from __future__ import annotations

import hashlib
import hmac
import json
import os
import unittest
from urllib.parse import urlencode
from unittest.mock import patch

from app.telegram_auth import TelegramAuthError, validate_init_data
from app.config import get_settings


BOT_TOKEN = "test-token-only-not-a-real-credential"


def signed_init_data(fields: dict[str, str], token: str = BOT_TOKEN) -> str:
    check = "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", token.encode("utf-8"), hashlib.sha256).digest()
    signature = hmac.new(secret, check.encode("utf-8"), hashlib.sha256).hexdigest()
    return urlencode([*fields.items(), ("hash", signature)])


class TelegramInitDataValidationTests(unittest.TestCase):
    def _fields(self, **overrides):
        values = {
            "auth_date": "1793900000",
            "user": json.dumps({"id": 123456789, "first_name": "Test"}, separators=(",", ":")),
            "query_id": "query-test",
        }
        values.update(overrides)
        return values

    def test_accepts_correctly_signed_recent_init_data(self):
        raw = signed_init_data(self._fields())
        result = validate_init_data(raw, BOT_TOKEN, max_age_seconds=600, now=1793900100)
        self.assertEqual(result["user"]["id"], 123456789)
        self.assertEqual(result["auth_date"], 1793900000)
        self.assertEqual(result["query_id"], "query-test")

    def test_rejects_signature_signed_by_another_bot_token(self):
        raw = signed_init_data(self._fields())
        with self.assertRaisesRegex(TelegramAuthError, "signature"):
            validate_init_data(raw, "different-token", max_age_seconds=600, now=1793900100)

    def test_rejects_modified_user_data_after_signing(self):
        raw = signed_init_data(self._fields())
        raw = raw.replace("123456789", "987654321")
        with self.assertRaises(TelegramAuthError):
            validate_init_data(raw, BOT_TOKEN, max_age_seconds=600, now=1793900100)

    def test_rejects_expired_init_data(self):
        raw = signed_init_data(self._fields(auth_date="1793899000"))
        with self.assertRaisesRegex(TelegramAuthError, "expired"):
            validate_init_data(raw, BOT_TOKEN, max_age_seconds=600, now=1793900100)

    def test_rejects_auth_date_more_than_30_seconds_in_the_future(self):
        raw = signed_init_data(self._fields(auth_date="1793900101"))
        with self.assertRaisesRegex(TelegramAuthError, "expired"):
            validate_init_data(raw, BOT_TOKEN, max_age_seconds=600, now=1793900100)

    def test_accepts_clock_skew_at_or_below_30_seconds(self):
        raw = signed_init_data(self._fields(auth_date="1793900130"))
        result = validate_init_data(raw, BOT_TOKEN, max_age_seconds=600, now=1793900100)
        self.assertEqual(result["user"]["id"], 123456789)

    def test_rejects_duplicate_query_fields(self):
        raw = signed_init_data(self._fields()) + "&auth_date=1793900000"
        with self.assertRaisesRegex(TelegramAuthError, "Duplicate"):
            validate_init_data(raw, BOT_TOKEN, max_age_seconds=600, now=1793900100)

    def test_rejects_missing_hash_and_invalid_hash_shape(self):
        fields = self._fields()
        raw_without_hash = urlencode(list(fields.items()))
        with self.assertRaises(TelegramAuthError):
            validate_init_data(raw_without_hash, BOT_TOKEN, max_age_seconds=600, now=1793900100)
        with self.assertRaises(TelegramAuthError):
            validate_init_data(raw_without_hash + "&hash=short", BOT_TOKEN, max_age_seconds=600, now=1793900100)

    def test_rejects_missing_or_non_numeric_auth_date_even_when_signed(self):
        for fields in (self._fields(auth_date=None), self._fields(auth_date="not-a-time")):
            cleaned = {key: value for key, value in fields.items() if value is not None}
            raw = signed_init_data(cleaned)
            with self.assertRaises(TelegramAuthError):
                validate_init_data(raw, BOT_TOKEN, max_age_seconds=600, now=1793900100)

    def test_rejects_invalid_json_or_user_id_type_even_when_signed(self):
        invalid_values = (
            self._fields(user="{not-json"),
            self._fields(user=json.dumps({"id": "123456789"})),
            self._fields(user=json.dumps(["123456789"])),
        )
        for fields in invalid_values:
            raw = signed_init_data(fields)
            with self.assertRaises(TelegramAuthError):
                validate_init_data(raw, BOT_TOKEN, max_age_seconds=600, now=1793900100)

    def test_rejects_empty_init_data_or_bot_token(self):
        with self.assertRaises(TelegramAuthError):
            validate_init_data("", BOT_TOKEN)
        with self.assertRaises(TelegramAuthError):
            validate_init_data(signed_init_data(self._fields()), "")


class ProductionConfigurationTests(unittest.TestCase):
    def test_production_refuses_development_auth(self):
        with patch.dict(os.environ, {
            "BOT_TOKEN": BOT_TOKEN,
            "BOT_USERNAME": "test_bot",
            "ENVIRONMENT": "production",
            "ALLOW_DEV_AUTH": "true",
            "PAYMENTS_MODE": "disabled",
            "STARS_MONTHLY_PRICE": "0",
        }, clear=True):
            with self.assertRaisesRegex(RuntimeError, "ALLOW_DEV_AUTH must be false"):
                get_settings()

    def test_production_settings_accept_secure_auth_and_keep_billing_off_by_default(self):
        with patch.dict(os.environ, {
            "BOT_TOKEN": BOT_TOKEN,
            "BOT_USERNAME": "test_bot",
            "ENVIRONMENT": "production",
            "ALLOW_DEV_AUTH": "false",
            "TELEGRAM_INITDATA_MAX_AGE_SECONDS": "600",
            "PAYMENTS_MODE": "disabled",
            "STARS_MONTHLY_PRICE": "0",
        }, clear=True):
            settings = get_settings()
        self.assertFalse(settings.allow_dev_auth)
        self.assertEqual(settings.initdata_max_age_seconds, 600)
        self.assertEqual(settings.payments_mode, "disabled")
        self.assertEqual(settings.stars_monthly_price, 0)

    def test_init_data_max_age_has_a_60_second_floor(self):
        with patch.dict(os.environ, {
            "BOT_TOKEN": BOT_TOKEN,
            "BOT_USERNAME": "test_bot",
            "ENVIRONMENT": "production",
            "ALLOW_DEV_AUTH": "false",
            "TELEGRAM_INITDATA_MAX_AGE_SECONDS": "1",
            "PAYMENTS_MODE": "disabled",
            "STARS_MONTHLY_PRICE": "0",
        }, clear=True):
            settings = get_settings()
        self.assertEqual(settings.initdata_max_age_seconds, 60)


if __name__ == "__main__":
    unittest.main()
