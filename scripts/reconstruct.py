#!/usr/bin/env python3
"""Rebuild the exact release source used by Docker, CI and local verification.

Only writes inside a NEW output directory. Never loads application configuration,
starts the bot, or touches a deployed database.
"""
from __future__ import annotations

import base64
import io
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile


def reconstruct(output: Path) -> Path:
    root = Path(__file__).resolve().parents[1]
    output.mkdir(parents=True, exist_ok=False)
    parts = sorted((root / "payload").glob("release-0.2.4.tar.xz.b64.part*"))
    if not parts:
        raise RuntimeError("Pinned release archive is missing")
    encoded = b"".join(path.read_bytes() for path in parts)
    archive = base64.b64decode(b"".join(encoded.split()), validate=True)
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:xz") as bundle:
        bundle.extractall(output, filter="data")
    source = output / "anti-scam-guardian"
    for name in ("scanner.py", "backup_supervisor.py", "restore_backup.py", "runtime_security_patch.py"):
        shutil.copy2(root / "overlays/app" / name, source / "app" / name)
    for name in ("apply-database-refund-patch.py", "apply_bot_operator_patch.py", "apply_product_limits_patch.py"):
        shutil.copy2(root / "overlays/app" / name, source / name)
    for test in (root / "overlays/tests").iterdir():
        if test.suffix in {".py", ".mjs"}:
            shutil.copy2(test, source / "tests" / test.name)
    for path in (root / "overlays/web").iterdir():
        if path.suffix == ".js":
            shutil.copy2(path, source / "web/src" / path.name)
        elif path.suffix == ".mjs":
            shutil.copy2(path, source / "web" / path.name)
    commands = [
        ["apply-database-refund-patch.py", "app/database.py"],
        ["apply_bot_operator_patch.py", "app/bot.py"],
        ["apply_product_limits_patch.py", "app/config.py", "app/database.py", "app/main.py"],
        ["-m", "app.runtime_security_patch", "app/runtime.py"],
    ]
    for args in commands:
        subprocess.run([sys.executable, *args], cwd=source, check=True)
    print(f"Release source ready: {source}")
    return source


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/reconstruct.py NEW_OUTPUT_DIRECTORY")
    reconstruct(Path(sys.argv[1]).resolve())
