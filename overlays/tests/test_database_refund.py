from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app import database


class StarRefundReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp.name, "refund-test.sqlite3")
        os.environ["DATABASE_PATH"] = self.db_path
        os.environ["ENVIRONMENT"] = "development"
        database.init_db()
        database.upsert_user(424242, "refund-test")

    def tearDown(self):
        os.environ.pop("DATABASE_PATH", None)
        self.temp.cleanup()

    def _expiry(self) -> datetime:
        with sqlite3.connect(self.db_path) as conn:
            value = conn.execute(
                "SELECT expires_at FROM subscriptions WHERE telegram_id=424242"
            ).fetchone()[0]
        return datetime.fromisoformat(value)

    def test_refunding_first_of_two_stacked_periods_moves_remaining_period_to_now(self):
        now = datetime.now(timezone.utc)
        self.assertTrue(database.activate_star_subscription("first", 424242, 100, "XTR", 30))
        self.assertTrue(database.activate_star_subscription("second", 424242, 100, "XTR", 30))
        self.assertGreater(self._expiry(), now + timedelta(days=59))

        self.assertTrue(database.record_star_refund("first"))
        remaining = self._expiry() - datetime.now(timezone.utc)
        self.assertGreater(remaining, timedelta(days=29))
        self.assertLess(remaining, timedelta(days=30, minutes=1))

    def test_late_refund_preserves_end_of_period_already_in_progress(self):
        start = datetime.now(timezone.utc)
        self.assertTrue(database.activate_star_subscription("first", 424242, 100, "XTR", 30))
        self.assertTrue(database.activate_star_subscription("second", 424242, 100, "XTR", 30))
        expected_end = start + timedelta(days=60)
        refund_time = start + timedelta(days=45)

        with patch.object(database, "_now", return_value=refund_time):
            self.assertTrue(database.record_star_refund("first"))

        self.assertLess(abs((self._expiry() - expected_end).total_seconds()), 2)


if __name__ == "__main__":
    unittest.main()
