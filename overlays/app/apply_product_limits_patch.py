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


def patch_config_source(source: str) -> str:
    source = _replace_once(
        source,
        "    free_scans_per_day: int\n    initdata_max_age_seconds: int",
        "    free_scans_per_day: int\n    pro_scans_per_day: int\n    initdata_max_age_seconds: int",
        "Pro scan limit setting field",
    )
    source = _replace_once(
        source,
        '        free_scans_per_day=max(0, _int("FREE_SCANS_PER_DAY", 5)),\n        initdata_max_age_seconds=',
        '        free_scans_per_day=max(0, _int("FREE_SCANS_PER_DAY", 5)),\n'
        '        pro_scans_per_day=max(1, _int("PRO_SCANS_PER_DAY", 100)),\n'
        '        initdata_max_age_seconds=',
        "Pro scan limit setting value",
    )
    ast.parse(source)
    return source


def patch_database_source(source: str) -> str:
    source = _replace_once(
        source,
        "def reserve_scan(telegram_id: int, kind: str, input_hash: str, free_limit: int) -> dict[str, Any]:",
        "def reserve_scan(telegram_id: int, kind: str, input_hash: str, free_limit: int, pro_limit: int = 100) -> dict[str, Any]:",
        "reserve_scan signature",
    )
    source = _replace_once(
        source,
        '''        if not premium and used >= free_limit:
            return {"allowed": False, "premium": False, "used_today": used, "scan_id": None}
        cursor = conn.execute(''',
        '''        limit = max(0, int(pro_limit if premium else free_limit))
        if used >= limit:
            return {
                "allowed": False,
                "premium": premium,
                "used_today": used,
                "scan_id": None,
                "limit": limit,
            }
        cursor = conn.execute(''',
        "separate Free and Pro daily limits",
    )
    source = _replace_once(
        source,
        '        return {"allowed": True, "premium": premium, "used_today": used + 1, "scan_id": int(cursor.lastrowid)}',
        '        return {"allowed": True, "premium": premium, "used_today": used + 1, "scan_id": int(cursor.lastrowid), "limit": limit}',
        "reservation response limit",
    )
    ast.parse(source)
    return source


def patch_main_source(source: str) -> str:
    source = _replace_once(
        source,
        '        "free_scans_per_day": settings.free_scans_per_day,\n        "scans_used_today": daily_scan_count(telegram_id),',
        '        "free_scans_per_day": settings.free_scans_per_day,\n'
        '        "pro_scans_per_day": settings.pro_scans_per_day,\n'
        '        "scans_used_today": daily_scan_count(telegram_id),',
        "current account Pro limit",
    )
    source = _replace_once(
        source,
        "    reservation = reserve_scan(telegram_id, request.kind, digest, settings.free_scans_per_day)",
        "    reservation = reserve_scan(telegram_id, request.kind, digest, settings.free_scans_per_day, settings.pro_scans_per_day)",
        "reservation call with both plan limits",
    )
    source = _replace_once(
        source,
        '''    if not reservation["allowed"]:
        raise HTTPException(status_code=402, detail="Daily free scan limit reached. Use /premium in the bot for Pro access.")''',
        '''    if not reservation["allowed"]:
        if reservation["premium"]:
            detail = f"Daily Pro scan limit reached ({settings.pro_scans_per_day} scans)."
        else:
            detail = "Daily free scan limit reached. Use /plans in the bot to compare plans."
        raise HTTPException(status_code=402, detail=detail)''',
        "plan-specific quota response",
    )
    source = _replace_once(
        source,
        '            "free_limit": settings.free_scans_per_day,\n            "premium": reservation["premium"],',
        '            "free_limit": settings.free_scans_per_day,\n'
        '            "pro_limit": settings.pro_scans_per_day,\n'
        '            "premium": reservation["premium"],',
        "scan response plan limits",
    )
    ast.parse(source)
    return source


def patch_product_sources(config_source: str, database_source: str, main_source: str) -> tuple[str, str, str]:
    """Apply the same explicit Free/Pro limits to settings, atomic quota reservation, and API."""
    return (
        patch_config_source(config_source),
        patch_database_source(database_source),
        patch_main_source(main_source),
    )


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit(
            "Usage: python apply_product_limits_patch.py app/config.py app/database.py app/main.py"
        )
    paths = [Path(value) for value in sys.argv[1:]]
    originals = [path.read_text(encoding="utf-8") for path in paths]
    patched = patch_product_sources(*originals)
    for path, content in zip(paths, patched, strict=True):
        path.write_text(content, encoding="utf-8")
        print(f"PATCHED {path}")


if __name__ == "__main__":
    main()
