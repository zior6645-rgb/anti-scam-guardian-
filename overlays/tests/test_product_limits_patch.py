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
    payments_mode: str
    stars_monthly_price: int

def get_settings():
    settings = Settings(
        free_scans_per_day=max(0, _int("FREE_SCANS_PER_DAY", 5)),
        payments_mode=os.getenv("PAYMENTS_MODE", "disabled").strip().lower(),
        stars_monthly_price=max(0, _int("STARS_MONTHLY_PRICE", 0)),
    )
    if settings.payments_mode == "telegram_stars" and settings.stars_monthly_price <= 0:
        raise RuntimeError("Set STARS_MONTHLY_PRICE to a positive integer to enable Stars billing")
    if settings.payments_mode == "telegram_stars" and not settings.admin_telegram_ids:
        raise RuntimeError("Set ADMIN_TELEGRAM_IDS before enabling live Stars billing")
    return settings
'''

DATABASE_FIXTURE = '''from typing import Any

def reserve_scan(telegram_id: int, kind: str, input_hash: str, free_limit: int) -> dict[str, Any]:
    now = _now()
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        premium = _premium_in_connection(conn, telegram_id, now)
        count_row = conn.execute("SELECT COUNT(*) AS n FROM scans WHERE telegram_id=?", (telegram_id,)).fetchone()
        used = int(count_row["n"] if count_row else 0)
        if not premium and used >= free_limit:
            return {"allowed": False, "premium": False, "used_today": used, "scan_id": None}
        cursor = conn.execute("INSERT INTO scans(telegram_id) VALUES (?)", (telegram_id,))
        return {"allowed": True, "premium": premium, "used_today": used + 1, "scan_id": int(cursor.lastrowid)}

def recent_scans(telegram_id: int, limit: int = 5) -> list[dict[str, Any]]:
    bounded = max(1, min(int(limit), 50))
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM scans WHERE telegram_id=? ORDER BY id DESC LIMIT ?", (telegram_id, bounded)).fetchall()
    return [dict(row) for row in rows]
'''

MAIN_FIXTURE = '''def health():
    return {"ok": True, "service": "anti-scam-guardian", "version": "0.2.4", "payments": settings.payments_mode}

def me(telegram_id):
    return {
        "authenticated": True,
        "premium": is_premium(telegram_id),
        "free_scans_per_day": settings.free_scans_per_day,
        "scans_used_today": daily_scan_count(telegram_id),
        "payments_mode": settings.payments_mode,
        "terms_accepted": has_accepted_terms(telegram_id),
        "url_provider_configured": bool(settings.phishtank_app_key),
    }

def history(telegram_id):
    premium = is_premium(telegram_id)
    return {"items": recent_scans(telegram_id, 50 if premium else 5), "premium": premium}

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
    def test_config_removes_billing_settings_and_forces_unlimited_free(self):
        patched = patch_config_source(CONFIG_FIXTURE)
        ast.parse(patched)
        self.assertIn("free_scans_per_day=0", patched)
        self.assertNotIn("PAYMENTS_MODE", patched)
        self.assertNotIn("STARS_MONTHLY_PRICE", patched)
        self.assertNotIn("payments_mode", patched)
        self.assertNotIn("stars_monthly_price", patched)

    def test_database_allows_scans_and_removes_history_limit(self):
        patched = patch_database_source(DATABASE_FIXTURE)
        ast.parse(patched)
        self.assertIn("premium = False", patched)
        self.assertNotIn("used >= free_limit", patched)
        self.assertIn('"unlimited": True', patched)
        self.assertNotIn("min(int(limit), 50)", patched)
        self.assertIn("1000000000", patched)

    def test_api_removes_paywall_and_returns_unlimited_history(self):
        patched = patch_main_source(MAIN_FIXTURE)
        ast.parse(patched)
        self.assertIn('"unlimited_scans": True', patched)
        self.assertIn("recent_scans(telegram_id, 1000000000)", patched)
        self.assertIn('"unlimited": True', patched)
        self.assertNotIn("payments_mode", patched)
        self.assertNotIn("Daily free scan limit reached", patched)
        self.assertNotIn("status_code=402", patched)

    def test_all_product_patches_are_idempotent(self):
        once = patch_product_sources(CONFIG_FIXTURE, DATABASE_FIXTURE, MAIN_FIXTURE)
        twice = patch_product_sources(*once)
        self.assertEqual(once, twice)

    def test_unknown_database_source_fails_closed(self):
        with self.assertRaises(ValueError):
            patch_database_source("def reserve_scan():\n    return {}\n")


if __name__ == "__main__":
    unittest.main()
