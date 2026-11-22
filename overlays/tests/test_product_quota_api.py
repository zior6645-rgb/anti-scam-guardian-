import os
import tempfile
import unittest
from dataclasses import replace
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
import app.main as main


class FreeUnlimitedApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        env = patch.dict(os.environ, {
            "DATABASE_PATH": os.path.join(self.temp.name, "unlimited-api.sqlite3"),
            "ENVIRONMENT": "development",
        })
        env.start()
        self.addCleanup(env.stop)
        config = patch.object(main, "settings", replace(
            main.settings,
            environment="development",
            allow_dev_auth=True,
            free_scans_per_day=0,
        ))
        config.start()
        self.addCleanup(config.stop)
        scanner = patch.object(main, "scan_url", AsyncMock(return_value={
            "risk_level": "no_obvious_flags",
            "flags": [],
            "subject": "example.com",
        }))
        self.scanner = scanner.start()
        self.addCleanup(scanner.stop)
        self.client = self.enterContext(TestClient(main.app))
        self.client.get("/api/me")

    def scan(self):
        return self.client.post("/api/scan", json={
            "kind": "url",
            "value": "https://example.com",
        })

    def test_account_and_scan_endpoints_are_free_and_unlimited(self):
        account = self.client.get("/api/me").json()
        self.assertFalse(account["premium"])
        self.assertEqual(account["free_scans_per_day"], 0)
        self.assertTrue(account["unlimited_scans"])
        self.assertNotIn("payments_mode", account)

        for index in range(12):
            response = self.scan()
            self.assertEqual(response.status_code, 200)
            usage = response.json()["usage"]
            self.assertFalse(usage["premium"])
            self.assertEqual(usage["free_limit"], 0)
            self.assertTrue(usage["unlimited"])

        self.assertEqual(self.scanner.await_count, 12)

    def test_history_endpoint_returns_more_than_the_old_free_limit(self):
        for _ in range(8):
            self.assertEqual(self.scan().status_code, 200)
        history = self.client.get("/api/history").json()
        self.assertTrue(history["unlimited"])
        self.assertFalse(history["premium"])
        self.assertEqual(len(history["items"]), 8)

    def test_provider_failure_does_not_consume_a_scan(self):
        self.scanner.side_effect = RuntimeError("private provider error")
        response = self.scan()
        self.assertEqual(response.status_code, 502)
        self.assertNotIn("private provider", response.text)

        self.scanner.side_effect = None
        self.assertEqual(self.scan().status_code, 200)

    def test_single_label_hostname_is_rejected_by_api_before_provider_call(self):
        response = self.client.post("/api/scan", json={
            "kind": "url",
            "value": "not-a-valid-url",
        })
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.scanner.await_count, 0)

    def test_invalid_input_does_not_call_provider(self):
        response = self.client.post("/api/scan", json={
            "kind": "url",
            "value": "javascript:alert(1)",
        })
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.scanner.await_count, 0)


if __name__ == "__main__":
    unittest.main()
