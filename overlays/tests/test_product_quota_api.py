"""Exercise assembled API + database, with only external scanning mocked."""
import os
import tempfile
import unittest
from dataclasses import replace
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from app import database
import app.main as main


class ProductQuotaApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.env = patch.dict(os.environ, {
            "DATABASE_PATH": os.path.join(self.temp.name, "quota-api.sqlite3"),
            "ENVIRONMENT": "development",
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        config = patch.object(main, "settings", replace(
            main.settings, environment="development", allow_dev_auth=True,
            free_scans_per_day=2, pro_scans_per_day=3, payments_mode="disabled",
        ))
        config.start()
        self.addCleanup(config.stop)
        scanner = patch.object(main, "scan_url", AsyncMock(return_value={
            "risk_level": "no_obvious_flags", "flags": [], "subject": "example.com",
        }))
        self.scanner = scanner.start()
        self.addCleanup(scanner.stop)
        self.client = self.enterContext(TestClient(main.app))
        self.client.get("/api/me")

    def scan(self):
        return self.client.post("/api/scan", json={"kind": "url", "value": "https://example.com"})

    def test_free_quota_matches_account_and_blocks_before_calling_provider(self):
        account = self.client.get("/api/me").json()
        self.assertEqual(account["free_scans_per_day"], 2)
        self.assertEqual(account["pro_scans_per_day"], 3)
        self.assertFalse(account["pro_checkout_enabled"])
        for expected in [1, 2]:
            response = self.scan()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["usage"]["used_today"], expected)
        self.assertEqual(self.scan().status_code, 402)
        self.assertEqual(self.scanner.await_count, 2)
        self.assertEqual(self.client.get("/api/me").json()["scans_used_today"], 2)

    def test_paid_activation_duplicate_delivery_and_refund_change_access(self):
        self.assertTrue(database.activate_star_subscription("test-charge", 0, 100, "XTR", 30))
        self.assertFalse(database.activate_star_subscription("test-charge", 0, 100, "XTR", 30))
        self.assertTrue(self.client.get("/api/me").json()["premium"])
        for _ in range(3):
            response = self.scan()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["usage"]["pro_limit"], 3)
        blocked = self.scan()
        self.assertEqual(blocked.status_code, 402)
        self.assertIn("Daily Pro", blocked.json()["detail"])
        self.assertTrue(database.begin_star_refund("test-charge"))
        self.assertTrue(database.record_star_refund("test-charge"))
        self.assertFalse(self.client.get("/api/me").json()["premium"])
        self.assertIn("Daily free", self.scan().json()["detail"])

    def test_provider_failure_returns_quota_and_does_not_leak_exception(self):
        self.scanner.side_effect = RuntimeError("private provider error")
        response = self.scan()
        self.assertEqual(response.status_code, 502)
        self.assertNotIn("private provider", response.text)
        self.assertEqual(self.client.get("/api/me").json()["scans_used_today"], 0)
        self.scanner.side_effect = None
        self.assertEqual(self.scan().status_code, 200)

    def test_invalid_input_does_not_consume_quota(self):
        response = self.client.post("/api/scan", json={"kind": "url", "value": "javascript:alert(1)"})
        self.assertEqual(response.status_code, 422)
        self.scanner.assert_not_awaited()
        self.assertEqual(self.client.get("/api/me").json()["scans_used_today"], 0)
