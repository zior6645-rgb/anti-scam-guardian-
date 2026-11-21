from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from app import database


class FreeUnlimitedRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp.name, "free-unlimited.sqlite3")
        self.env = patch.dict(os.environ, {
            "DATABASE_PATH": self.db_path,
            "ENVIRONMENT": "development",
        }, clear=False)
        self.env.start()
        database.init_db()
        database.upsert_user(810001, "free-user")

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_more_than_previous_daily_limit_is_allowed(self):
        for index in range(20):
            reservation = database.reserve_scan(810001, "url", "hash-" + str(index), 5)
            self.assertTrue(reservation["allowed"])
            self.assertFalse(reservation["premium"])
            self.assertTrue(reservation["unlimited"])
            database.complete_scan(reservation["scan_id"], {"risk_level": "no_obvious_flags"})

    def test_history_is_not_capped_at_five_or_fifty(self):
        for index in range(12):
            reservation = database.reserve_scan(810001, "url", "history-" + str(index), 5)
            self.assertTrue(reservation["allowed"])
            database.complete_scan(reservation["scan_id"], {"risk_level": "no_obvious_flags"})
        rows = database.recent_scans(810001, 1_000_000_000)
        self.assertEqual(len(rows), 12)


if __name__ == "__main__":
    unittest.main()
