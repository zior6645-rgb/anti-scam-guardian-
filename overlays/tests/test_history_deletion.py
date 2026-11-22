from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from app import database


class HistoryDeletionDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {
            "DATABASE_PATH": os.path.join(self.temp.name, "history-delete.sqlite3"),
            "ENVIRONMENT": "development",
        }, clear=False)
        self.env.start()
        database.init_db()
        database.upsert_user(101, "owner")
        database.upsert_user(202, "other")

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def _scan(self, telegram_id: int, value: str) -> int:
        reservation = database.reserve_scan(telegram_id, "wallet", value, 0)
        database.complete_scan(
            reservation["scan_id"],
            {"risk_level": "caution", "subject": "TON address scan"},
        )
        return reservation["scan_id"]

    def test_delete_one_scan_only_for_its_owner(self):
        owned = self._scan(101, "owner-scan")
        other = self._scan(202, "other-scan")

        self.assertTrue(database.delete_scan(101, owned))
        self.assertFalse(database.delete_scan(101, other))
        self.assertEqual(database.recent_scans(101, 100), [])
        self.assertEqual([item["id"] for item in database.recent_scans(202, 100)], [other])

    def test_delete_all_scans_removes_only_the_callers_history(self):
        first = self._scan(101, "owner-one")
        second = self._scan(101, "owner-two")
        other = self._scan(202, "other-one")

        self.assertEqual(database.delete_all_scans(101), 2)
        self.assertEqual(database.recent_scans(101, 100), [])
        self.assertEqual([item["id"] for item in database.recent_scans(202, 100)], [other])
        self.assertFalse(database.delete_scan(101, first))
        self.assertFalse(database.delete_scan(101, second))


if __name__ == "__main__":
    unittest.main()
