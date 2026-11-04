from __future__ import annotations

import unittest
from urllib.parse import quote
from types import SimpleNamespace
from unittest.mock import patch

from app.scanner import (
    normalize_url_input,
    scan_ton_account,
    scan_ton_jetton,
    scan_url,
)

RAW_ADDRESS = "0:" + "a" * 64


class FakeResponse:
    def __init__(self, status_code: int, body):
        self.status_code = status_code
        self._body = body

    def json(self):
        return self._body


class FakeAsyncClient:
    def __init__(self, response, *args, **kwargs):
        self.response = response
        self.requested_url = None
        self.requested_post = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url):
        self.requested_url = url
        return self.response

    async def post(self, url, **kwargs):
        self.requested_post = (url, kwargs)
        return self.response


class ScannerReleaseTests(unittest.IsolatedAsyncioTestCase):
    async def _run_ton(self, func, response):
        client = FakeAsyncClient(response)
        settings = SimpleNamespace(ton_api_base_url="https://tonapi.io/v2", tonapi_key="")
        with (
            patch("app.scanner.normalize_ton_address", return_value=RAW_ADDRESS),
            patch("app.scanner.get_settings", return_value=settings),
            patch("app.scanner.httpx.AsyncClient", return_value=client),
        ):
            result = await func("sample-address")
        return result, client.requested_url

    async def test_wallet_uses_accounts_endpoint_and_longer_timeout(self):
        result, url = await self._run_ton(
            scan_ton_account,
            FakeResponse(200, {"status": "active", "is_scam": False, "balance": 10}),
        )
        self.assertTrue(url.endswith("/accounts/" + quote(RAW_ADDRESS, safe="")))
        self.assertEqual(result["risk_level"], "not_assessed")
        self.assertIs(result["provider_is_scam"], False)

    async def test_wallet_provider_scam_is_high_risk(self):
        result, _ = await self._run_ton(
            scan_ton_account,
            FakeResponse(200, {"status": "active", "is_scam": True}),
        )
        self.assertEqual(result["risk_level"], "high")

    async def test_wallet_missing_scam_indicator_is_insufficient_data(self):
        result, _ = await self._run_ton(
            scan_ton_account,
            FakeResponse(200, {"status": "active"}),
        )
        self.assertEqual(result["risk_level"], "insufficient_data")

    async def test_jetton_uses_jettons_endpoint_and_preserves_metadata(self):
        result, url = await self._run_ton(
            scan_ton_jetton,
            FakeResponse(200, {
                "metadata": {"name": "Example Token", "symbol": "EXT", "decimals": "9"},
                "verification": "whitelist",
                "mintable": False,
                "total_supply": "1000000000",
                "holders_count": 123,
            }),
        )
        self.assertTrue(url.endswith("/jettons/" + quote(RAW_ADDRESS, safe="")))
        self.assertEqual(result["token_name"], "Example Token")
        self.assertEqual(result["token_symbol"], "EXT")
        self.assertEqual(result["verification"], "whitelist")
        self.assertEqual(result["risk_level"], "provider_whitelisted")

    async def test_jetton_blacklist_is_high_risk(self):
        result, _ = await self._run_ton(
            scan_ton_jetton,
            FakeResponse(200, {"metadata": {}, "verification": "blacklist"}),
        )
        self.assertEqual(result["risk_level"], "high")

    async def test_jetton_graylist_is_caution(self):
        result, _ = await self._run_ton(
            scan_ton_jetton,
            FakeResponse(200, {"metadata": {}, "verification": "graylist"}),
        )
        self.assertEqual(result["risk_level"], "caution")

    async def test_jetton_is_scam_true_is_high_even_without_blacklist(self):
        result, _ = await self._run_ton(
            scan_ton_jetton,
            FakeResponse(200, {"metadata": {}, "verification": "unknown", "is_scam": True}),
        )
        self.assertEqual(result["risk_level"], "high")

    async def test_jetton_not_found_has_insufficient_data(self):
        result, _ = await self._run_ton(scan_ton_jetton, FakeResponse(404, {}))
        self.assertEqual(result["provider_status"], 404)
        self.assertEqual(result["risk_level"], "insufficient_data")

    def test_url_normalization_rejects_private_network_targets(self):
        for value in ("http://127.0.0.1/", "http://10.0.0.5/", "http://localhost/"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_url_input(value)

    def test_url_normalization_rejects_non_web_schemes(self):
        with self.assertRaises(ValueError):
            normalize_url_input("javascript:alert(1)")

    async def test_url_scanner_does_not_share_without_explicit_consent(self):
        settings = SimpleNamespace(phishtank_app_key="test-key")
        with patch("app.scanner.get_settings", return_value=settings), patch(
            "app.scanner._check_phishtank"
        ) as external_lookup:
            result = await scan_url("https://example.com", share_with_phishtank=False)
        external_lookup.assert_not_awaited()
        self.assertEqual(result["threat_intelligence"]["status"], "not_checked_no_consent")
        self.assertFalse(result["external_lookup_shared"])


if __name__ == "__main__":
    unittest.main()
