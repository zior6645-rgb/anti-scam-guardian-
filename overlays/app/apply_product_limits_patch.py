from __future__ import annotations

import ast
import re
import sys
from pathlib import Path


def _replace_once(source: str, old: str, new: str, label: str) -> str:
    if new and new in source:
        return source
    count = source.count(old)
    if count != 1:
        raise ValueError(f"Expected exactly one {label} anchor, found {count}")
    return source.replace(old, new, 1)


def _remove_optional(source: str, old: str, label: str) -> str:
    count = source.count(old)
    if count > 1:
        raise ValueError(f"Expected at most one {label} block, found {count}")
    return source.replace(old, "", 1) if count else source


def _contains_limit_name(node: ast.AST) -> bool:
    return any(isinstance(child, ast.Name) and child.id == "limit" for child in ast.walk(node))


class _RemoveHistoryUpperBound(ast.NodeTransformer):
    def visit_Call(self, node: ast.Call):
        self.generic_visit(node)
        if isinstance(node.func, ast.Name) and node.func.id == "min":
            candidates = [arg for arg in node.args if _contains_limit_name(arg)]
            if candidates:
                return candidates[0]
        return node


def _patch_recent_scans_unlimited(source: str) -> str:
    tree = ast.parse(source)
    matches = [
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "recent_scans"
    ]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one recent_scans function, found {len(matches)}")

    node = matches[0]
    node = _RemoveHistoryUpperBound().visit(node)
    args = node.args.posonlyargs + node.args.args
    defaults_start = len(args) - len(node.args.defaults)
    for index, default in enumerate(node.args.defaults):
        if args[defaults_start + index].arg == "limit":
            node.args.defaults[index] = ast.Constant(value=1_000_000_000)

    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and isinstance(child.value, str):
            child.value = re.sub(r"\bLIMIT\s+\d+\b", "LIMIT 1000000000", child.value, flags=re.IGNORECASE)

    ast.fix_missing_locations(node)
    lines = source.splitlines(keepends=True)
    start_line = node.lineno
    end_line = node.end_lineno
    replacement = ast.unparse(node) + "\n"
    patched = "".join(lines[:start_line - 1]) + replacement + "".join(lines[end_line:])
    ast.parse(patched)
    return patched


def patch_config_source(source: str) -> str:
    source = _replace_once(
        source,
        '        free_scans_per_day=max(0, _int("FREE_SCANS_PER_DAY", 5)),',
        "        free_scans_per_day=0,",
        "unlimited Free scan setting",
    )
    source = _remove_optional(
        source,
        "    payments_mode: str\n    stars_monthly_price: int\n",
        "paid settings fields",
    )
    source = _remove_optional(
        source,
        '        payments_mode=os.getenv("PAYMENTS_MODE", "disabled").strip().lower(),\n'
        '        stars_monthly_price=max(0, _int("STARS_MONTHLY_PRICE", 0)),\n',
        "paid settings values",
    )
    source = _remove_optional(
        source,
        '    if settings.payments_mode not in {"disabled", "telegram_stars"}:\n'
        '        raise RuntimeError("PAYMENTS_MODE must be \'disabled\' or \'telegram_stars\'")\n',
        "payment mode validation",
    )
    source = _remove_optional(
        source,
        '    if settings.payments_mode == "telegram_stars" and settings.stars_monthly_price <= 0:\n'
        '        raise RuntimeError("Set STARS_MONTHLY_PRICE to a positive integer to enable Stars billing")\n'
        '    if settings.payments_mode == "telegram_stars" and not settings.admin_telegram_ids:\n'
        '        raise RuntimeError("Set ADMIN_TELEGRAM_IDS before enabling live Stars billing")\n',
        "Stars billing validation",
    )
    ast.parse(source)
    return source


def patch_database_source(source: str) -> str:
    source = _replace_once(
        source,
        "        premium = _premium_in_connection(conn, telegram_id, now)",
        "        premium = False",
        "disable paid entitlement checks for scan access",
    )
    source = _replace_once(
        source,
        '''        if not premium and used >= free_limit:
            return {"allowed": False, "premium": False, "used_today": used, "scan_id": None}
        cursor = conn.execute(''',
        '''        # Free plan scans are unlimited; no daily quota check is applied.
        cursor = conn.execute(''',
        "remove daily scan quota rejection",
    )
    source = _replace_once(
        source,
        '        return {"allowed": True, "premium": premium, "used_today": used + 1, "scan_id": int(cursor.lastrowid)}',
        '        return {"allowed": True, "premium": False, "used_today": used + 1, "scan_id": int(cursor.lastrowid), "limit": 0, "unlimited": True}',
        "unlimited scan reservation response",
    )
    source = _patch_recent_scans_unlimited(source)
    ast.parse(source)
    return source


def patch_main_source(source: str) -> str:
    source = _replace_once(
        source,
        '        "premium": is_premium(telegram_id),\n'
        '        "free_scans_per_day": settings.free_scans_per_day,\n'
        '        "scans_used_today": daily_scan_count(telegram_id),\n'
        '        "payments_mode": settings.payments_mode,\n'
        '        "terms_accepted": has_accepted_terms(telegram_id),\n'
        '        "url_provider_configured": bool(settings.phishtank_app_key),',
        '        "premium": False,\n'
        '        "free_scans_per_day": 0,\n'
        '        "unlimited_scans": True,\n'
        '        "scans_used_today": daily_scan_count(telegram_id),\n'
        '        "url_provider_configured": bool(settings.phishtank_app_key),',
        "free unlimited account response",
    )
    source = _replace_once(
        source,
        '    premium = is_premium(telegram_id)\n'
        '    return {"items": recent_scans(telegram_id, 50 if premium else 5), "premium": premium}',
        '    return {"items": recent_scans(telegram_id, 1000000000), "premium": False, "unlimited": True}',
        "unlimited scan history response",
    )
    source = _replace_once(
        source,
        '    return {"ok": True, "service": "anti-scam-guardian", "version": "0.2.4", "payments": settings.payments_mode}',
        '    return {"ok": True, "service": "anti-scam-guardian", "version": "0.2.4"}',
        "health response without payment state",
    )
    source = _replace_once(
        source,
        "    reservation = reserve_scan(telegram_id, request.kind, digest, settings.free_scans_per_day)",
        "    reservation = reserve_scan(telegram_id, request.kind, digest, 0)",
        "unlimited scan reservation call",
    )
    source = _replace_once(
        source,
        '''    if not reservation["allowed"]:
        raise HTTPException(status_code=402, detail="Daily free scan limit reached. Use /premium in the bot for Pro access.")''',
        '''    if not reservation["allowed"]:
        raise HTTPException(status_code=503, detail="Could not reserve this scan. Please retry.")''',
        "remove quota payment prompt",
    )
    source = _replace_once(
        source,
        '            "free_limit": settings.free_scans_per_day,\n'
        '            "premium": reservation["premium"],',
        '            "free_limit": 0,\n'
        '            "premium": False,\n'
        '            "unlimited": True,',
        "unlimited scan usage response",
    )
    ast.parse(source)
    return source


def patch_product_sources(config_source: str, database_source: str, main_source: str) -> tuple[str, str, str]:
    """Force free/unlimited account, scan, and history behavior across the API and database."""
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
