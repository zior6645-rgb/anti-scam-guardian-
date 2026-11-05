from __future__ import annotations

import ast
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


BOT_PATH = Path(__file__).resolve().parents[1] / "app" / "bot.py"
PRODUCT_PAYLOAD = "antiscam:pro:monthly:v1"


def _source_expression(predicate, label: str) -> ast.expr:
    """Read the real, already-patched production bot and locate one guard expression."""
    tree = ast.parse(BOT_PATH.read_text(encoding="utf-8"))
    matches = []
    for node in ast.walk(tree):
        if isinstance(node, ast.If) and predicate(ast.unparse(node.test)):
            matches.append(node.test)
        elif isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "allowed"
            for target in node.targets
        ) and predicate(ast.unparse(node.value)):
            matches.append(node.value)
    if len(matches) != 1:
        raise AssertionError(f"Expected one {label} expression in {BOT_PATH}; found {len(matches)}")
    return matches[0]


def _evaluate(expression: ast.expr, **values):
    # This evaluates only a guard expression parsed from the repository's production bot.
    # Restrict globals to the primitives and modules referenced by these boolean guards.
    safe_globals = {"__builtins__": {"bool": bool}, "os": os}
    return bool(eval(compile(ast.Expression(expression), str(BOT_PATH), "eval"), safe_globals, values))


class TelegramStarsProductionGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pre_checkout_guard = _source_expression(
            lambda text: all(
                term in text
                for term in (
                    "query.invoice_payload",
                    "query.currency",
                    "query.total_amount",
                    "settings.payments_mode",
                    "settings.stars_monthly_price",
                )
            ),
            "pre-checkout",
        )
        cls.success_guard = _source_expression(
            lambda text: all(
                term in text
                for term in (
                    "payment.currency",
                    "payment.invoice_payload",
                    "payment.total_amount",
                    "payment.telegram_payment_charge_id",
                )
            ),
            "successful-payment",
        )

    def _settings(self, **overrides):
        values = {
            "payments_mode": "telegram_stars",
            "stars_monthly_price": 125,
            "admin_telegram_ids": [424242],
        }
        values.update(overrides)
        return SimpleNamespace(**values)

    def _query(self, **overrides):
        values = {
            "invoice_payload": PRODUCT_PAYLOAD,
            "currency": "XTR",
            "total_amount": 125,
            "from_user": SimpleNamespace(id=424242),
        }
        values.update(overrides)
        return SimpleNamespace(**values)

    def _payment(self, **overrides):
        values = {
            "currency": "XTR",
            "invoice_payload": PRODUCT_PAYLOAD,
            "total_amount": 125,
            "telegram_payment_charge_id": "test-charge-001",
        }
        values.update(overrides)
        return SimpleNamespace(**values)

    def _checkout(self, settings=None, query=None, accepted=True):
        return _evaluate(
            self.pre_checkout_guard,
            settings=settings or self._settings(),
            query=query or self._query(),
            has_accepted_terms=lambda _user_id: accepted,
        )

    def _successful_payment(self, payment=None):
        return _evaluate(self.success_guard, payment=payment or self._payment())

    def test_valid_stars_pre_checkout_is_accepted(self):
        with patch.dict(os.environ, {"SUPPORT_CONTACT": "@verified_support"}):
            self.assertTrue(self._checkout())

    def test_pre_checkout_rejected_when_billing_is_disabled(self):
        with patch.dict(os.environ, {"SUPPORT_CONTACT": "@verified_support"}):
            self.assertFalse(self._checkout(settings=self._settings(payments_mode="disabled")))

    def test_pre_checkout_rejected_when_price_is_zero(self):
        with patch.dict(os.environ, {"SUPPORT_CONTACT": "@verified_support"}):
            self.assertFalse(self._checkout(settings=self._settings(stars_monthly_price=0)))

    def test_pre_checkout_rejected_without_refund_admin(self):
        with patch.dict(os.environ, {"SUPPORT_CONTACT": "@verified_support"}):
            self.assertFalse(self._checkout(settings=self._settings(admin_telegram_ids=[])))

    def test_pre_checkout_rejected_without_support_contact(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(self._checkout())

    def test_pre_checkout_rejected_for_wrong_currency_payload_or_amount(self):
        with patch.dict(os.environ, {"SUPPORT_CONTACT": "@verified_support"}):
            self.assertFalse(self._checkout(query=self._query(currency="USD")))
            self.assertFalse(self._checkout(query=self._query(invoice_payload="other-product")))
            self.assertFalse(self._checkout(query=self._query(total_amount=126)))

    def test_pre_checkout_rejected_when_terms_were_not_accepted(self):
        with patch.dict(os.environ, {"SUPPORT_CONTACT": "@verified_support"}):
            self.assertFalse(self._checkout(accepted=False))

    def test_valid_positive_stars_success_payment_is_eligible_for_fulfillment(self):
        self.assertTrue(self._successful_payment())

    def test_success_payment_guard_rejects_wrong_currency_or_product(self):
        self.assertFalse(self._successful_payment(self._payment(currency="USD")))
        self.assertFalse(self._successful_payment(self._payment(invoice_payload="other-product")))

    def test_success_payment_guard_rejects_zero_negative_amount_or_missing_charge_id(self):
        self.assertFalse(self._successful_payment(self._payment(total_amount=0)))
        self.assertFalse(self._successful_payment(self._payment(total_amount=-1)))
        self.assertFalse(self._successful_payment(self._payment(telegram_payment_charge_id="")))


if __name__ == "__main__":
    unittest.main()
