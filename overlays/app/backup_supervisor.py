from __future__ import annotations

import asyncio
import base64
import gzip
import hashlib
import json
import logging
import os
import re
import signal
import sqlite3
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

LOGGER = logging.getLogger("antiscam.backup")
MAGIC = b"ASGDBK01"
NONCE_BYTES = 12
TAG_BYTES = 16
CHUNK_BYTES = 1024 * 1024
MAX_TELEGRAM_UPLOAD_BYTES = 45 * 1024 * 1024
RETRY_SECONDS = 15 * 60


def _load_key(value: str | None = None) -> bytes:
    encoded = (value if value is not None else os.getenv("BACKUP_ENCRYPTION_KEY", "")).strip()
    if not encoded:
        raise RuntimeError("BACKUP_ENCRYPTION_KEY is not configured")
    try:
        key = base64.urlsafe_b64decode(encoded.encode("ascii"))
    except Exception as exc:
        raise RuntimeError("BACKUP_ENCRYPTION_KEY must be a URL-safe Base64 32-byte key") from exc
    if len(key) != 32:
        raise RuntimeError("BACKUP_ENCRYPTION_KEY must decode to exactly 32 bytes")
    return key


def encrypt_file(source: Path, destination: Path, key: bytes) -> None:
    """Encrypt a file using streaming AES-256-GCM with an authenticated header."""
    if len(key) != 32:
        raise ValueError("AES-256-GCM requires a 32-byte key")
    nonce = os.urandom(NONCE_BYTES)
    encryptor = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
    encryptor.authenticate_additional_data(MAGIC)
    with source.open("rb") as src, destination.open("wb") as dst:
        dst.write(MAGIC)
        dst.write(nonce)
        while chunk := src.read(CHUNK_BYTES):
            dst.write(encryptor.update(chunk))
        dst.write(encryptor.finalize())
        dst.write(encryptor.tag)
        dst.flush()
        os.fsync(dst.fileno())


def decrypt_file(source: Path, destination: Path, key: bytes) -> None:
    """Authenticate and decrypt an ASGDBK01 file; destination is written only after tag validation."""
    if len(key) != 32:
        raise ValueError("AES-256-GCM requires a 32-byte key")
    total_size = source.stat().st_size
    minimum_size = len(MAGIC) + NONCE_BYTES + TAG_BYTES
    if total_size < minimum_size:
        raise ValueError("Backup file is too small or truncated")
    with source.open("rb") as src:
        header = src.read(len(MAGIC))
        if header != MAGIC:
            raise ValueError("Unknown backup format")
        nonce = src.read(NONCE_BYTES)
        src.seek(total_size - TAG_BYTES)
        tag = src.read(TAG_BYTES)
        src.seek(len(MAGIC) + NONCE_BYTES)
        decryptor = Cipher(algorithms.AES(key), modes.GCM(nonce, tag)).decryptor()
        decryptor.authenticate_additional_data(MAGIC)
        with tempfile.TemporaryDirectory(prefix="asg-decrypt-") as temp_dir:
            staged = Path(temp_dir) / "authenticated-output.tmp"
            remaining = total_size - minimum_size
            with staged.open("wb") as out:
                while remaining:
                    chunk = src.read(min(CHUNK_BYTES, remaining))
                    if not chunk:
                        raise ValueError("Backup file ended unexpectedly")
                    remaining -= len(chunk)
                    out.write(decryptor.update(chunk))
                out.write(decryptor.finalize())
            destination.parent.mkdir(parents=True, exist_ok=True)
            with staged.open("rb") as src_staged, destination.open("wb") as dst:
                while chunk := src_staged.read(CHUNK_BYTES):
                    dst.write(chunk)
                dst.flush()
                os.fsync(dst.fileno())


def create_sqlite_snapshot(database_path: Path, snapshot_path: Path) -> None:
    """Create a transactionally consistent SQLite snapshot and verify its integrity."""
    if not database_path.is_file():
        raise FileNotFoundError(f"Database file does not exist: {database_path}")
    source_uri = database_path.resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(source_uri, uri=True, timeout=30) as source:
        with sqlite3.connect(snapshot_path, timeout=30) as destination:
            source.backup(destination, pages=256, sleep=0.05)
            check = destination.execute("PRAGMA integrity_check").fetchone()
            if not check or check[0] != "ok":
                raise RuntimeError(f"SQLite integrity_check failed: {check[0] if check else 'no result'}")


def gzip_file(source: Path, destination: Path) -> None:
    with source.open("rb") as src, destination.open("wb") as raw_dst:
        with gzip.GzipFile(fileobj=raw_dst, mode="wb", compresslevel=6, mtime=0) as dst:
            while chunk := src.read(CHUNK_BYTES):
                dst.write(chunk)


def _first_private_admin_id(raw_ids: str) -> int:
    candidates = [int(item) for item in re.findall(r"-?\d+", raw_ids)]
    for candidate in candidates:
        if candidate > 0:
            return candidate
    raise RuntimeError("No positive private administrator ID is configured in ADMIN_TELEGRAM_IDS")


def send_telegram_document(token: str, chat_id: int, document_path: Path, caption: str) -> dict:
    """Upload one encrypted backup through the official Telegram Bot API."""
    size = document_path.stat().st_size
    if size > MAX_TELEGRAM_UPLOAD_BYTES:
        raise RuntimeError(
            f"Encrypted backup is {size} bytes; the safe upload limit is {MAX_TELEGRAM_UPLOAD_BYTES} bytes"
        )
    boundary = "----AntiScamGuardian" + os.urandom(12).hex()
    filename = document_path.name
    document = document_path.read_bytes()
    body = bytearray()

    def add_field(name: str, value: str) -> None:
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        body.extend(value.encode("utf-8"))
        body.extend(b"\r\n")

    add_field("chat_id", str(chat_id))
    add_field("caption", caption[:900])
    body.extend(f"--{boundary}\r\n".encode())
    body.extend(
        f'Content-Disposition: form-data; name="document"; filename="{filename}"\r\n'.encode()
    )
    body.extend(b"Content-Type: application/octet-stream\r\n\r\n")
    body.extend(document)
    body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode())

    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendDocument",
        data=bytes(body),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # Never log the request URL: it contains the bot token.
        detail = exc.read(2048).decode("utf-8", errors="replace")
        raise RuntimeError(f"Telegram rejected the backup upload (HTTP {exc.code}): {detail}") from None
    except Exception as exc:
        raise RuntimeError(f"Telegram backup upload failed: {type(exc).__name__}") from None
    if not payload.get("ok"):
        raise RuntimeError(f"Telegram backup upload was not accepted: {payload.get('description', 'unknown error')}")
    return payload


def run_backup_once() -> dict:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN is not configured; cannot deliver the encrypted backup")
    chat_id = _first_private_admin_id(os.getenv("ADMIN_TELEGRAM_IDS", ""))
    key = _load_key()
    database_path = Path(os.getenv("DATABASE_PATH", "/data/guardian.sqlite3"))
    backup_interval = int(os.getenv("BACKUP_INTERVAL_SECONDS", "86400"))
    if backup_interval < 3600:
        raise RuntimeError("BACKUP_INTERVAL_SECONDS must be at least 3600 seconds")

    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y%m%d-%H%M%SZ")
    with tempfile.TemporaryDirectory(prefix="asg-backup-") as temp_dir:
        temp = Path(temp_dir)
        snapshot = temp / "guardian.sqlite3"
        compressed = temp / "guardian.sqlite3.gz"
        encrypted = temp / f"antiscam-guardian-{stamp}.asgbak"
        create_sqlite_snapshot(database_path, snapshot)
        gzip_file(snapshot, compressed)
        encrypt_file(compressed, encrypted, key)
        size = encrypted.stat().st_size
        digest = hashlib.sha256(encrypted.read_bytes()).hexdigest()
        caption = (
            "AntiScam Guardian — encrypted automatic SQLite backup\n"
            f"UTC: {now.isoformat(timespec='seconds')}\n"
            f"Size: {size} bytes\n"
            f"SHA-256: {digest}\n"
            "Keep the decryption key offline. This file is encrypted."
        )
        result = send_telegram_document(token, chat_id, encrypted, caption)
        return {
            "timestamp": now.isoformat(timespec="seconds"),
            "size": size,
            "sha256": digest,
            "message_id": result.get("result", {}).get("message_id"),
            "chat_id": chat_id,
        }


def _state_path() -> Path:
    return Path(os.getenv("BACKUP_STATE_PATH", "/data/.asg_backup_state.json"))


def _last_success() -> datetime | None:
    try:
        value = json.loads(_state_path().read_text(encoding="utf-8"))["last_success_utc"]
        parsed = datetime.fromisoformat(value)
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None


def _write_success_state(timestamp: str) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(path.name + ".tmp")
    temp_path.write_text(json.dumps({"last_success_utc": timestamp}), encoding="utf-8")
    os.replace(temp_path, path)


async def backup_scheduler() -> None:
    interval = int(os.getenv("BACKUP_INTERVAL_SECONDS", "86400"))
    while True:
        last = _last_success()
        due = last is None or datetime.now(timezone.utc) - last >= timedelta(seconds=interval)
        if due:
            try:
                result = await asyncio.to_thread(run_backup_once)
                _write_success_state(result["timestamp"])
                LOGGER.info(
                    "Encrypted database backup delivered to administrator chat; size=%s sha256=%s message_id=%s",
                    result["size"], result["sha256"], result["message_id"],
                )
            except Exception as exc:
                LOGGER.error("Automatic database backup failed; it will be retried: %s", exc)
        await asyncio.sleep(RETRY_SECONDS)


async def supervise() -> int:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    LOGGER.info("Starting AntiScam Guardian runtime with automatic encrypted daily backups")
    child = await asyncio.create_subprocess_exec(sys.executable, "-m", "app.runtime")
    scheduler = asyncio.create_task(backup_scheduler(), name="encrypted-daily-backup")
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            pass
    child_wait = asyncio.create_task(child.wait())
    stop_wait = asyncio.create_task(stop_event.wait())
    try:
        done, _ = await asyncio.wait(
            {child_wait, stop_wait}, return_when=asyncio.FIRST_COMPLETED
        )
        if stop_wait in done and stop_event.is_set() and child.returncode is None:
            LOGGER.info("Shutdown requested; stopping application runtime")
            child.terminate()
            try:
                await asyncio.wait_for(child.wait(), timeout=15)
            except asyncio.TimeoutError:
                child.kill()
                await child.wait()
            return 0
        return int(child.returncode or 0)
    finally:
        scheduler.cancel()
        stop_wait.cancel()
        if child.returncode is None:
            child.terminate()
            try:
                await asyncio.wait_for(child.wait(), timeout=10)
            except asyncio.TimeoutError:
                child.kill()
                await child.wait()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(supervise()))
