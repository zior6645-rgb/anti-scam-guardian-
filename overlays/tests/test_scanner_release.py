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

    def raise_for_status(self):
        if self.status_code >= 400:
            raise ValueError("HTTP error")


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

    def test_url_normalization_rejects_single_label_text(self):
        with self.assertRaisesRegex(ValueError, "complete domain name"):
            normalize_url_input("not-a-valid-url")

    def test_url_normalization_rejects_whitespace_and_backslashes(self):
        for value in ("https://exa mple.com", r"https://example.com\@evil.test"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_url_input(value)

    def test_url_normalization_rejects_embedded_credentials(self):
        with self.assertRaisesRegex(ValueError, "embedded credentials"):
            normalize_url_input("https://user:pass@example.com/login")

    def test_url_normalization_canonicalizes_bare_domain(self):
        self.assertEqual(normalize_url_input("WWW.Google.com"), "https://www.google.com/")

    def test_registrable_domain_uses_public_suffix_list_for_multi_label_suffix(self):
        from app.scanner import get_registrable_domain
        self.assertEqual(get_registrable_domain("login.example.co.uk"), "example.co.uk")

    def test_registrable_domain_respects_private_hosting_suffixes(self):
        from app.scanner import get_registrable_domain
        self.assertEqual(get_registrable_domain("login.customer.github.io"), "customer.github.io")

    async def test_brand_name_in_attacker_subdomain_is_flagged_and_not_clean(self):
        settings = SimpleNamespace(phishtank_app_key="")
        with patch("app.scanner.get_settings", return_value=settings):
            result = await scan_url("https://google.com.example.com")
        self.assertEqual(result["registrable_domain"], "example.com")
        self.assertIn("google", result["hostname"])
        self.assertTrue(any("brand name 'google'" in flag for flag in result["flags"]))
        self.assertIn(result["risk_level"], {"caution", "high"})
        self.assertNotEqual(result["risk_level"], "no_obvious_flags")

    async def test_any_reported_indicator_prevents_clean_verdict(self):
        settings = SimpleNamespace(phishtank_app_key="")
        with patch("app.scanner.get_settings", return_value=settings):
            result = await scan_url("http://bit.ly/redirect?next=https%3A%2F%2Fexample.com")
        self.assertTrue(result["flags"])
        self.assertNotEqual(result["risk_level"], "no_obvious_flags")

    async def test_lookalike_brand_domain_is_flagged(self):
        settings = SimpleNamespace(phishtank_app_key="")
        with patch("app.scanner.get_settings", return_value=settings):
            result = await scan_url("https://g00gle.com/login")
        self.assertTrue(any("resembles the brand 'google'" in flag for flag in result["flags"]))
        self.assertNotEqual(result["risk_level"], "no_obvious_flags")

    async def test_confirmed_phishtank_result_is_high_risk_when_user_consents(self):
        settings = SimpleNamespace(phishtank_app_key="test-key")
        with (
            patch("app.scanner.get_settings", return_value=settings),
            patch(
                "app.scanner._check_phishtank",
                return_value={
                    "provider": "PhishTank",
                    "status": "confirmed_phishing",
                    "phish_id": "123",
                },
            ) as external_lookup,
        ):
            result = await scan_url("https://example.com/bad", share_with_phishtank=True)
        external_lookup.assert_awaited_once()
        self.assertEqual(result["risk_level"], "high")
        self.assertEqual(result["heuristic_score"], 100)
        self.assertEqual(result["method"], "heuristics_plus_phishtank")

    async def test_url_scanner_does_not_share_without_explicit_consent(self):
        settings = SimpleNamespace(phishtank_app_key="test-key")
        with patch("app.scanner.get_settings", return_value=settings), patch(
            "app.scanner._check_phishtank"
        ) as external_lookup:
            result = await scan_url("https://example.com", share_with_phishtank=False)
        external_lookup.assert_not_awaited()
        self.assertEqual(result["threat_intelligence"]["status"], "not_checked_no_consent")
        self.assertFalse(result["external_lookup_shared"])

    async def test_url_disclaimer_explains_phishtank_was_not_queried_without_consent(self):
        settings = SimpleNamespace(phishtank_app_key="")
        with patch("app.scanner.get_settings", return_value=settings):
            result = await scan_url("http://wallet-connect-airdrop.invalid/seed")

        self.assertEqual(result["risk_level"], "caution")
        self.assertEqual(result["threat_intelligence"]["status"], "not_configured")
        self.assertIn("no PhishTank app key is configured", result["disclaimer"])
        self.assertIn("not sent because external sharing was not approved", result["disclaimer"])
        self.assertIn("local_heuristics_only", result["method"])
        self.assertIn("does not prove safety", result["disclaimer"])

    async def test_phishtank_rate_limit_still_records_external_sharing(self):
        settings = SimpleNamespace(phishtank_app_key="")
        client = FakeAsyncClient(FakeResponse(429, {}))
        with (
            patch("app.scanner.get_settings", return_value=settings),
            patch("app.scanner.httpx.AsyncClient", return_value=client),
        ):
            result = await scan_url("https://example.com", share_with_phishtank=True)

        self.assertEqual(result["threat_intelligence"]["status"], "rate_limited")
        self.assertTrue(result["external_lookup_shared"])
        self.assertEqual(result["method"], "local_heuristics_only")

    async def test_phishtank_low_volume_lookup_works_without_app_key_after_consent(self):
        settings = SimpleNamespace(phishtank_app_key="")
        client = FakeAsyncClient(FakeResponse(200, {"results": {"in_database": "no"}}))
        with (
            patch("app.scanner.get_settings", return_value=settings),
            patch("app.scanner.httpx.AsyncClient", return_value=client),
        ):
            result = await scan_url("https://example.com", share_with_phishtank=True)

        self.assertIsNotNone(client.requested_post)
        url, kwargs = client.requested_post
        self.assertEqual(url, "https://checkurl.phishtank.com/checkurl/")
        self.assertNotIn("app_key", kwargs["data"])
        self.assertEqual(result["threat_intelligence"]["status"], "not_listed")
        self.assertTrue(result["external_lookup_shared"])
        self.assertEqual(result["method"], "heuristics_plus_phishtank")

    async def test_documentation_domain_has_no_obvious_flags_without_external_sharing(self):
        settings = SimpleNamespace(phishtank_app_key="")
        with patch("app.scanner.get_settings", return_value=settings):
            result = await scan_url("https://example.com")
        self.assertEqual(result["risk_level"], "no_obvious_flags")
        self.assertEqual(result["flags"], [])
        self.assertEqual(result["method"], "local_heuristics_only")
        self.assertFalse(result["external_lookup_shared"])

    async def test_suspicious_tld_is_reported_as_caution(self):
        settings = SimpleNamespace(phishtank_app_key="")
        with patch("app.scanner.get_settings", return_value=settings):
            result = await scan_url("https://account-security.click/login")
        self.assertEqual(result["risk_level"], "caution")
        self.assertTrue(any("TLD" in flag for flag in result["flags"]))

    async def test_redirect_parameter_is_reported(self):
        settings = SimpleNamespace(phishtank_app_key="")
        with patch("app.scanner.get_settings", return_value=settings):
            result = await scan_url("http://example.com/login?redirect=https%3A%2F%2Fother.example")
        self.assertTrue(any("redirect-style parameters" in flag for flag in result["flags"]))
        self.assertGreaterEqual(result["heuristic_score"], 20)


if __name__ == "__main__":
    unittest.main()
