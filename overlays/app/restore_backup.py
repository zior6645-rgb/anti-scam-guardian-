from __future__ import annotations

import argparse
import gzip
import sqlite3
import tempfile
from pathlib import Path

try:
    from .backup_supervisor import _load_key, decrypt_file
except ImportError:  # Support direct execution from the extracted app directory.
    from backup_supervisor import _load_key, decrypt_file


def restore(backup_path: Path, destination: Path, force: bool = False) -> None:
    if destination.exists() and not force:
        raise FileExistsError(f"Refusing to overwrite existing file: {destination}; use --force")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="asg-restore-") as temp_dir:
        compressed = Path(temp_dir) / "guardian.sqlite3.gz"
        decrypt_file(backup_path, compressed, _load_key())
        staged_db = Path(temp_dir) / "guardian.sqlite3"
        with gzip.open(compressed, "rb") as src, staged_db.open("wb") as dst:
            while chunk := src.read(1024 * 1024):
                dst.write(chunk)
        with sqlite3.connect(staged_db) as conn:
            result = conn.execute("PRAGMA integrity_check").fetchone()
            if not result or result[0] != "ok":
                raise RuntimeError("Restored SQLite database failed integrity_check")
        if destination.exists() and force:
            destination.unlink()
        staged_db.replace(destination)


def main() -> None:
    parser = argparse.ArgumentParser(description="Restore an encrypted AntiScam Guardian backup")
    parser.add_argument("backup", type=Path, help="Telegram-downloaded .asgbak file")
    parser.add_argument("destination", type=Path, help="Output SQLite file path")
    parser.add_argument("--force", action="store_true", help="Allow replacing destination")
    args = parser.parse_args()
    restore(args.backup, args.destination, args.force)
    print(f"Restored and verified SQLite database: {args.destination}")


if __name__ == "__main__":
    main()
