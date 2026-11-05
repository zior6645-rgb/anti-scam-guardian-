from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app import database


class ProductQuotaRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp.name, "product-limits.sqlite3")
        self.environment = patch.dict(
            os.environ,
            {"DATABASE_PATH": self.db_path, "ENVIRONMENT": "development"},
            clear=False,
        )
        self.environment.start()
        database.init_db()
        database.upsert_user(810001, "free-user")
        database.upsert_user(810002, "pro-user")
        self.assertTrue(database.activate_star_subscription("pro-limit-test", 810002, 100, "XTR", 30))

    def tearDown(self):
        self.environment.stop()
        self.temp.cleanup()

    def _use_scan(self, telegram_id: int, index: int, free_limit: int, pro_limit: int):
        reservation = database.reserve_scan(
            telegram_id,
            "url",
            f"hash-{telegram_id}-{index}",
            free_limit,
            pro_limit,
        )
        if reservation["allowed"]:
            database.complete_scan(reservation["scan_id"], {"risk_level": "no_obvious_flags"})
        return reservation

    def test_free_plan_allows_five_and_blocks_sixth(self):
        for i in range(5):
            result = self._use_scan(810001, i, 5, 100)
            self.assertTrue(result["allowed"])
            self.assertFalse(result["premium"])
            self.assertEqual(result["limit"], 5)
        blocked = self._use_scan(810001, 5, 5, 100)
        self.assertFalse(blocked["allowed"])
        self.assertFalse(blocked["premium"])
        self.assertEqual(blocked["limit"], 5)
        self.assertEqual(blocked["used_today"], 5)

    def test_pro_plan_allows_one_hundred_and_blocks_one_hundred_first(self):
        for i in range(100):
            result = self._use_scan(810002, i, 5, 100)
            self.assertTrue(result["allowed"], f"Pro scan {i + 1} should be allowed")
            self.assertTrue(result["premium"])
            self.assertEqual(result["limit"], 100)
        blocked = self._use_scan(810002, 100, 5, 100)
        self.assertFalse(blocked["allowed"])
        self.assertTrue(blocked["premium"])
        self.assertEqual(blocked["limit"], 100)
        self.assertEqual(blocked["used_today"], 100)

    def test_free_user_is_not_promoted_by_pro_limit(self):
        result = self._use_scan(810001, 0, 5, 100)
        self.assertEqual(result["limit"], 5)
        self.assertFalse(result["premium"])


if __name__ == "__main__":
    unittest.main()
