from __future__ import annotations

import ast
import sys
from pathlib import Path


def _replace_once(source: str, old: str, new: str, label: str) -> str:
    if new in source:
        return source
    count = source.count(old)
    if count != 1:
        raise ValueError(f"Expected exactly one {label} anchor, found {count}")
    return source.replace(old, new, 1)


def patch_database_source(source: str) -> str:
    additions = '''


def delete_scan(telegram_id: int, scan_id: int) -> bool:
    """Delete one scan only when it belongs to the authenticated Telegram user."""
    with _connect() as conn:
        cursor = conn.execute(
            "DELETE FROM scans WHERE id=? AND telegram_id=?",
            (scan_id, telegram_id),
        )
    return cursor.rowcount == 1


def delete_all_scans(telegram_id: int) -> int:
    """Delete every scan-history row owned by the authenticated Telegram user."""
    with _connect() as conn:
        cursor = conn.execute(
            "DELETE FROM scans WHERE telegram_id=?",
            (telegram_id,),
        )
    return max(0, int(cursor.rowcount))
'''
    if "def delete_scan(" in source and "def delete_all_scans(" in source:
        return source
    source = _replace_once(
        source,
        "\n\ndef is_premium(telegram_id: int) -> bool:",
        additions + "\n\ndef is_premium(telegram_id: int) -> bool:",
        "database history deletion insertion",
    )
    ast.parse(source)
    return source


def patch_main_source(source: str) -> str:
    if '@app.delete("/api/history/{scan_id}")' in source and '@app.delete("/api/history")' in source:
        return source

    source = _replace_once(
        source,
        "    daily_scan_count,\n    has_accepted_terms,",
        "    daily_scan_count,\n    delete_all_scans,\n    delete_scan,\n    has_accepted_terms,",
        "database deletion imports",
    )

    old = '''@app.get("/api/history")
def history(x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data")) -> dict:
    telegram_id, username = _authorized_user(x_telegram_init_data)
    upsert_user(telegram_id, username)
    return {"items": recent_scans(telegram_id, 1000000000), "premium": False, "unlimited": True}


@app.post("/api/scan")'''
    new = '''@app.get("/api/history")
def history(x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data")) -> dict:
    telegram_id, username = _authorized_user(x_telegram_init_data)
    upsert_user(telegram_id, username)
    return {"items": recent_scans(telegram_id, 1000000000), "premium": False, "unlimited": True}


@app.delete("/api/history/{scan_id}")
def delete_history_item(
    scan_id: int,
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
) -> dict:
    telegram_id, username = _authorized_user(x_telegram_init_data)
    upsert_user(telegram_id, username)
    if not delete_scan(telegram_id, scan_id):
        raise HTTPException(status_code=404, detail="Scan not found in your history.")
    return {"deleted": True, "scan_id": scan_id}


@app.delete("/api/history")
def delete_history_all(
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
) -> dict:
    telegram_id, username = _authorized_user(x_telegram_init_data)
    upsert_user(telegram_id, username)
    return {"deleted_count": delete_all_scans(telegram_id)}


@app.post("/api/scan")'''
    source = _replace_once(source, old, new, "history API route insertion")
    ast.parse(source)
    return source


def apply_history_deletion(database_path: Path, main_path: Path) -> bool:
    changed = False
    for path, transform in (
        (database_path, patch_database_source),
        (main_path, patch_main_source),
    ):
        before = path.read_text(encoding="utf-8")
        after = transform(before)
        if after != before:
            path.write_text(after, encoding="utf-8")
            changed = True
    return changed


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: python apply_history_deletion_patch.py app/database.py app/main.py")
    changed = apply_history_deletion(Path(sys.argv[1]), Path(sys.argv[2]))
    print("PATCHED user-owned scan history deletion" if changed else "History deletion already patched")
