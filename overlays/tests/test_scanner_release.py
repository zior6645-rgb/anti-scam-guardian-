from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.scanner import scan_url, scan_ton_account


RAW_ADDRESS = "0:" + "a" * 64


class FakeResponse:
    def __init__(self, status_code: int, body):
        self.status_code = status_code
        self._body = body

    def json(self):
        return self._body


class FakeAsyncClient:
    def __init__(self, response):
        self.response = response
        self.requested_url = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url):
        self.requested_url = url
        return self.response


class ScannerReleaseTests(unittest.IsolatedAsyncioTestCase):
    async def run_scan(self, kind: str, status: int, body):
        client = FakeAsyncClient(FakeResponse(status, body))
        settings = SimpleNamespace(
            ton_api_base_url="https://tonapi.io/v2",
            tonapi_key="",
        )
        with (
            patch("app.scanner.normalize_ton_address", return_value=RAW_ADDRESS),
            patch("app.scanner.get_settings", return_value=settings),
            patch("app.scanner.httpx.AsyncClient", return_value=client),
        ):
            result = await scan_ton_account("sample-address", kind)
        return result, client.requested_url

    async def test_jetton_uses_jetton_endpoint_and_preserves_metadata(self):
        body = {
            "metadata": {"name": "Example Token", "symbol": "EXT", "decimals": "9"},
            "verification": "whitelist",
            "mintable": False,
            "total_supply": "1000000000",
            "holders_count": 123,
        }
        result, url = await self.run_scan("token", 200, body)
        self.assertTrue(url.endswith("/jettons/" + RAW_ADDRESS))
        self.assertEqual(result["method"], "tonapi_jetton_master_metadata")
        self.assertEqual(result["jetton_name"], "Example Token")
        self.assertEqual(result["jetton_symbol"], "EXT")
        self.assertEqual(result["jetton_verification"], "whitelist")
        self.assertEqual(result["risk_level"], "not_assessed")

    async def test_jetton_blacklist_is_high_risk(self):
        result, _ = await self.run_scan(
            "token",
            200,
            {"metadata": {"name": "Bad Token"}, "verification": "blacklist"},
        )
        self.assertEqual(result["risk_level"], "high")
        self.assertIn("blacklist", " ".join(result["flags"]).lower())

    async def test_jetton_graylist_is_caution(self):
        result, _ = await self.run_scan(
            "token",
            200,
            {"metadata": {}, "verification": "graylist"},
        )
        self.assertEqual(result["risk_level"], "caution")

    async def test_wallet_is_scam_true_is_high_risk(self):
        result, url = await self.run_scan(
            "wallet",
            200,
            {"status": "active", "is_scam": True, "balance": 1},
        )
        self.assertTrue(url.endswith("/accounts/" + RAW_ADDRESS))
        self.assertEqual(result["risk_level"], "high")
        self.assertIs(result["provider_is_scam"], True)

    async def test_wallet_is_scam_false_is_not_a_safety_verdict(self):
        result, _ = await self.run_scan(
            "wallet",
            200,
            {"status": "active", "is_scam": False},
        )
        self.assertEqual(result["risk_level"], "not_assessed")
        self.assertIs(result["provider_is_scam"], False)

    async def test_provider_404_returns_insufficient_data(self):
        result, _ = await self.run_scan("token", 404, {})
        self.assertEqual(result["risk_level"], "insufficient_data")
        self.assertEqual(result["provider_status"], 404)

    def test_non_global_ip_is_high_risk_heuristic(self):
        result = scan_url("http://127.0.0.1/login")
        self.assertEqual(result["risk_level"], "high")
        self.assertTrue(any("not globally routable" in flag for flag in result["flags"]))

    def test_non_web_scheme_is_rejected(self):
        with self.assertRaises(ValueError):
            scan_url("javascript:alert(1)")


if __name__ == "__main__":
    unittest.main()
