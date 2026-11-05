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

    def test_pending_refund_is_reserved_once_then_completed_once(self):
        self.assertTrue(database.activate_star_subscription("pending-1", 424242, 100, "XTR", 30))
        self.assertTrue(database.begin_star_refund("pending-1"))
        self.assertFalse(database.is_premium(424242))
        charge = database.get_star_charge("pending-1")
        self.assertFalse(charge["refunded"])
        self.assertTrue(charge["refund_pending"])
        self.assertFalse(database.begin_star_refund("pending-1"))

        self.assertTrue(database.record_star_refund("pending-1"))
        charge = database.get_star_charge("pending-1")
        self.assertTrue(charge["refunded"])
        self.assertFalse(charge["refund_pending"])
        self.assertFalse(database.record_star_refund("pending-1"))

    def test_releasing_pending_refund_requires_explicit_local_release(self):
        self.assertTrue(database.activate_star_subscription("pending-2", 424242, 100, "XTR", 30))
        self.assertTrue(database.begin_star_refund("pending-2"))
        self.assertFalse(database.is_premium(424242))
        self.assertTrue(database.cancel_star_refund("pending-2"))
        self.assertTrue(database.is_premium(424242))
        charge = database.get_star_charge("pending-2")
        self.assertFalse(charge["refunded"])
        self.assertFalse(charge["refund_pending"])
        self.assertTrue(database.begin_star_refund("pending-2"))

    def test_unknown_charge_cannot_be_reserved_for_refund(self):
        self.assertFalse(database.begin_star_refund("not-a-charge"))
        self.assertIsNone(database.get_star_charge("not-a-charge"))

    def test_pending_refund_on_one_charge_does_not_hide_another_unpaid_period(self):
        now = datetime.now(timezone.utc)
        self.assertTrue(database.activate_star_subscription("pending-first", 424242, 100, "XTR", 30))
        self.assertTrue(database.activate_star_subscription("refund-second", 424242, 100, "XTR", 30))
        self.assertTrue(database.begin_star_refund("pending-first"))
        self.assertFalse(database.is_premium(424242))
        self.assertTrue(database.record_star_refund("refund-second"))
        remaining = self._expiry() - datetime.now(timezone.utc)
        self.assertGreater(remaining, timedelta(days=29))
        self.assertLess(remaining, timedelta(days=30, minutes=1))
        self.assertTrue(database.get_star_charge("pending-first")["refund_pending"])
        self.assertFalse(database.is_premium(424242))
        self.assertTrue(database.cancel_star_refund("pending-first"))
        self.assertTrue(database.is_premium(424242))

    def test_recent_star_charges_are_newest_first_and_show_refund_state(self):
        self.assertTrue(database.activate_star_subscription("charge-old", 424242, 100, "XTR", 30))
        self.assertTrue(database.activate_star_subscription("charge-new", 424242, 150, "XTR", 30))
        self.assertTrue(database.begin_star_refund("charge-new"))
        rows = database.recent_star_charges(10)
        self.assertEqual(rows[0]["charge_id"], "charge-new")
        self.assertEqual(rows[0]["refund_status"], "pending")
        self.assertEqual(rows[1]["charge_id"], "charge-old")
        self.assertEqual(rows[1]["refund_status"], "none")
        self.assertLessEqual(len(database.recent_star_charges(1000)), 25)


    def test_duplicate_successful_payment_charge_id_only_grants_one_period(self):
        self.assertTrue(database.activate_star_subscription("charge-idempotency", 424242, 125, "XTR", 30))
        first_expiry = self._expiry()

        self.assertFalse(database.activate_star_subscription("charge-idempotency", 424242, 125, "XTR", 30))
        second_expiry = self._expiry()

        self.assertEqual(first_expiry, second_expiry)
        self.assertTrue(database.is_premium(424242))
        charge = database.get_star_charge("charge-idempotency")
        self.assertEqual(charge["amount"], 125)
        self.assertEqual(charge["currency"], "XTR")


if __name__ == "__main__":
    unittest.main()
