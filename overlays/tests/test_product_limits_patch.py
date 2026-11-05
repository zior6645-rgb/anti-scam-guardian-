from __future__ import annotations

import ast
import unittest

from apply_product_limits_patch import (
    patch_config_source,
    patch_database_source,
    patch_main_source,
    patch_product_sources,
)


CONFIG_FIXTURE = '''from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    free_scans_per_day: int
    initdata_max_age_seconds: int

def get_settings():
    settings = Settings(
        free_scans_per_day=max(0, _int("FREE_SCANS_PER_DAY", 5)),
        initdata_max_age_seconds=max(60, _int("TELEGRAM_INITDATA_MAX_AGE_SECONDS", 86400)),
    )
    return settings
'''

DATABASE_FIXTURE = '''from typing import Any

def reserve_scan(telegram_id: int, kind: str, input_hash: str, free_limit: int) -> dict[str, Any]:
    """Atomically reserve a scan slot before calling external providers."""
    now = _now()
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        stale_before = (now - timedelta(minutes=10)).isoformat()
        conn.execute(
            "DELETE FROM scans WHERE result_json=? AND created_at<?",
            (json.dumps({"status": "reserved"}), stale_before),
        )
        premium = _premium_in_connection(conn, telegram_id, now)
        count_row = conn.execute(
            "SELECT COUNT(*) AS n FROM scans WHERE telegram_id=? AND created_at>=?",
            (telegram_id, now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()),
        ).fetchone()
        used = int(count_row["n"] if count_row else 0)
        if not premium and used >= free_limit:
            return {"allowed": False, "premium": False, "used_today": used, "scan_id": None}
        cursor = conn.execute(
            "INSERT INTO scans(telegram_id, kind, input_hash, result_json, created_at) VALUES (?, ?, ?, ?, ?)",
            (telegram_id, kind, input_hash, json.dumps({"status": "reserved"}), now.isoformat()),
        )
        return {"allowed": True, "premium": premium, "used_today": used + 1, "scan_id": int(cursor.lastrowid)}
'''

MAIN_FIXTURE = '''def me(telegram_id):
    return {
        "authenticated": True,
        "premium": is_premium(telegram_id),
        "free_scans_per_day": settings.free_scans_per_day,
        "scans_used_today": daily_scan_count(telegram_id),
    }

async def scan(telegram_id, request, normalized_value):
    digest = hashlib.sha256(normalized_value.encode("utf-8")).hexdigest()
    reservation = reserve_scan(telegram_id, request.kind, digest, settings.free_scans_per_day)
    if not reservation["allowed"]:
        raise HTTPException(status_code=402, detail="Daily free scan limit reached. Use /premium in the bot for Pro access.")
    return {
        "result": {},
        "usage": {
            "used_today": reservation["used_today"],
            "free_limit": settings.free_scans_per_day,
            "premium": reservation["premium"],
        },
    }
'''


class ProductLimitPatchTests(unittest.TestCase):
    def test_settings_adds_bounded_pro_limit_default(self):
        patched = patch_config_source(CONFIG_FIXTURE)
        ast.parse(patched)
        self.assertIn("pro_scans_per_day: int", patched)
        self.assertIn('pro_scans_per_day=max(1, _int("PRO_SCANS_PER_DAY", 100))', patched)

    def test_reservation_enforces_free_and_pro_limits_separately(self):
        patched = patch_database_source(DATABASE_FIXTURE)
        ast.parse(patched)
        self.assertIn("pro_limit: int = 100", patched)
        self.assertIn("limit = max(0, int(pro_limit if premium else free_limit))", patched)
        self.assertIn('"limit": limit', patched)
        self.assertNotIn("if not premium and used >= free_limit", patched)

    def test_api_returns_plan_limits_and_plan_specific_limit_errors(self):
        patched = patch_main_source(MAIN_FIXTURE)
        ast.parse(patched)
        self.assertIn('"pro_scans_per_day": settings.pro_scans_per_day', patched)
        self.assertIn("settings.free_scans_per_day, settings.pro_scans_per_day", patched)
        self.assertIn("Daily Pro scan limit reached", patched)
        self.assertIn('"pro_limit": settings.pro_scans_per_day', patched)

    def test_combined_patch_is_idempotent(self):
        once = patch_product_sources(CONFIG_FIXTURE, DATABASE_FIXTURE, MAIN_FIXTURE)
        twice = patch_product_sources(*once)
        self.assertEqual(once, twice)

    def test_unknown_source_fails_closed(self):
        with self.assertRaises(ValueError):
            patch_database_source("def reserve_scan():\n    return {}\n")


if __name__ == "__main__":
    unittest.main()
