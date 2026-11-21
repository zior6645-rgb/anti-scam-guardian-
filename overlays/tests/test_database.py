from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from app import database


class FreeUnlimitedDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp.name, "database-test.sqlite3")
        self.env = patch.dict(os.environ, {
            "DATABASE_PATH": self.db_path,
            "ENVIRONMENT": "development",
        }, clear=False)
        self.env.start()
        database.init_db()
        database.upsert_user(552211, "free-unlimited-test")

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def _record_scan(self, index: int):
        reservation = database.reserve_scan(
            552211,
            "url",
            "database-scan-" + str(index),
            5,
        )
        self.assertTrue(reservation["allowed"])
        self.assertFalse(reservation["premium"])
        self.assertTrue(reservation["unlimited"])
        database.complete_scan(
            reservation["scan_id"],
            {"risk_level": "no_obvious_flags", "subject": "example.com"},
        )

    def test_free_user_can_scan_more_than_five_times(self):
        for index in range(15):
            self._record_scan(index)
        self.assertEqual(database.daily_scan_count(552211), 15)

    def test_free_user_can_read_more_than_five_history_items(self):
        for index in range(12):
            self._record_scan(index)
        history = database.recent_scans(552211, 1_000_000_000)
        self.assertEqual(len(history), 12)


if __name__ == "__main__":
    unittest.main()
