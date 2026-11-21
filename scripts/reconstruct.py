#!/usr/bin/env python3
"""Rebuild the exact release source used by Docker, CI and local verification.

Only writes inside a NEW output directory. Never loads application configuration,
starts the bot, or touches a deployed database.
"""
from __future__ import annotations

import base64
import ast
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
    # The pinned archive contains an obsolete API test that expects the TON
    # Connect manifest to return 200. The wallet-free release intentionally
    # removes that endpoint; retain the rest of the API test suite.
    legacy_api_test = source / "tests" / "test_api.py"
    if legacy_api_test.is_file():
        legacy = legacy_api_test.read_text(encoding="utf-8")
        tree = ast.parse(legacy)
        removed = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                retained = []
                for member in node.body:
                    if (
                        isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef))
                        and member.name == "test_tonconnect_manifest_requires_configured_https_origin"
                    ):
                        removed += 1
                    else:
                        retained.append(member)
                node.body = retained
        if removed != 1:
            raise RuntimeError("Could not locate the obsolete TON Connect manifest API test")
        legacy_api_test.write_text(ast.unparse(tree) + "\n", encoding="utf-8")
    for name in ("scanner.py", "backup_supervisor.py", "restore_backup.py", "runtime_security_patch.py"):
        shutil.copy2(root / "overlays/app" / name, source / "app" / name)
    for name in (
        "apply_product_limits_patch.py",
        "apply_free_mode_patch.py",
        "apply_wallet_removal_patch.py",
    ):
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
        ["apply_product_limits_patch.py", "app/config.py", "app/database.py", "app/main.py"],
        ["apply_free_mode_patch.py", "app/bot.py"],
        ["apply_wallet_removal_patch.py", "app"],
        ["-m", "app.runtime_security_patch", "app/runtime.py"],
    ]
    for args in commands:
        subprocess.run([sys.executable, *args], cwd=source, check=True)

    manifest = source / "app" / "static" / "tonconnect-manifest.json"
    if manifest.exists():
        raise RuntimeError("TON Connect manifest file remains after backend patching")

    # Every production Python patcher must be safe to reapply. Compare the
    # assembled outputs byte-for-byte after a second pass.
    patched_paths = [
        source / "app" / "database.py",
        source / "app" / "bot.py",
        source / "app" / "config.py",
        source / "app" / "main.py",
        source / "app" / "legal.py",
        source / "app" / "runtime.py",
    ]
    first_pass = {path: path.read_bytes() for path in patched_paths}
    for args in commands:
        subprocess.run([sys.executable, *args], cwd=source, check=True)
    changed = [
        str(path.relative_to(source))
        for path in patched_paths
        if path.read_bytes() != first_pass[path]
    ]
    if changed:
        raise RuntimeError(
            "Production patchers are not idempotent; second pass changed: "
            + ", ".join(changed)
        )
    if manifest.exists():
        raise RuntimeError("TON Connect manifest file reappeared after the second patch pass")
    print("All production Python patchers are idempotent.")
    print("TON Connect backend route and manifest are removed.")
    print(f"Release source ready: {source}")
    return source


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/reconstruct.py NEW_OUTPUT_DIRECTORY")
    reconstruct(Path(sys.argv[1]).resolve())
