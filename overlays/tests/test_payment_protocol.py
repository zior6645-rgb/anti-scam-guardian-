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


class RefundHandlerExecutionTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        source = BOT_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        functions = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "refund_payment"
        ]
        if len(functions) != 1:
            raise AssertionError(f"Expected one production refund_payment handler, found {len(functions)}")
        functions[0].decorator_list = []
        module = ast.Module(
            body=[
                ast.ImportFrom(
                    module="__future__",
                    names=[ast.alias(name="annotations")],
                    level=0,
                ),
                functions[0],
            ],
            type_ignores=[],
        )
        ast.fix_missing_locations(module)
        cls.refund_code = compile(module, str(BOT_PATH), "exec")

    class FakeMessage:
        def __init__(self, text="/refund charge-001", user_id=424242, chat_type="private"):
            self.text = text
            self.from_user = SimpleNamespace(id=user_id)
            self.chat = SimpleNamespace(type=chat_type)
            self.replies = []

        async def answer(self, value):
            self.replies.append(value)

    class FakeBot:
        def __init__(self, result=True, error=None, events=None):
            self.result = result
            self.error = error
            self.events = events if events is not None else []
            self.calls = 0

        async def refund_star_payment(self, **kwargs):
            self.calls += 1
            self.events.append("telegram")
            if self.error:
                raise self.error
            return self.result

    def _handler(self, *, charge=None, reserve=True, record=True, bot_result=True, bot_error=None, events=None):
        state = {
            "charge": charge or {
                "refunded": False,
                "refund_pending": False,
                "currency": "XTR",
                "telegram_id": 777,
            }
        }
        calls = events if events is not None else []

        def get_charge(_charge_id):
            calls.append("lookup")
            return state["charge"]

        def begin(_charge_id):
            calls.append("reserve")
            if reserve:
                state["charge"]["refund_pending"] = True
            return reserve

        def record_refund(_charge_id):
            calls.append("record")
            if isinstance(record, Exception):
                raise record
            if record:
                state["charge"]["refund_pending"] = False
                state["charge"]["refunded"] = True
            return record

        class Logger:
            def exception(self, *args, **kwargs):
                calls.append("logged_exception")

            def critical(self, *args, **kwargs):
                calls.append("logged_critical")

            def error(self, *args, **kwargs):
                calls.append("logged_error")

        namespace = {
            "settings": SimpleNamespace(admin_telegram_ids={424242}),
            "get_star_charge": get_charge,
            "begin_star_refund": begin,
            "record_star_refund": record_refund,
            "logger": Logger(),
        }
        exec(self.refund_code, namespace)
        bot = self.FakeBot(result=bot_result, error=bot_error, events=calls)
        return namespace["refund_payment"], bot, state, calls

    async def test_refund_reserves_before_remote_call_and_reconciles_after_acceptance(self):
        handler, bot, state, calls = self._handler()
        message = self.FakeMessage()

        await handler(message, bot)

        self.assertEqual(calls[:4], ["lookup", "reserve", "telegram", "record"])
        self.assertEqual(bot.calls, 1)
        self.assertTrue(state["charge"]["refunded"])
        self.assertFalse(state["charge"]["refund_pending"])
        self.assertTrue(any("reconciled" in reply for reply in message.replies))

    async def test_uncertain_telegram_result_keeps_charge_pending_and_blocks_retry(self):
        handler, bot, state, calls = self._handler(bot_error=RuntimeError("network outcome unknown"))
        message = self.FakeMessage()

        await handler(message, bot)
        self.assertEqual(bot.calls, 1)
        self.assertTrue(state["charge"]["refund_pending"])
        self.assertFalse(state["charge"]["refunded"])

        retry_handler, retry_bot, _, retry_calls = self._handler(
            charge=state["charge"],
            reserve=True,
        )
        retry_message = self.FakeMessage()
        await retry_handler(retry_message, retry_bot)
        self.assertEqual(retry_bot.calls, 0)
        self.assertNotIn("reserve", retry_calls)
        self.assertTrue(any("already pending" in reply for reply in retry_message.replies))

    async def test_telegram_rejection_keeps_pending_without_local_success_record(self):
        handler, bot, state, calls = self._handler(bot_result=False)
        message = self.FakeMessage()

        await handler(message, bot)
        self.assertEqual(bot.calls, 1)
        self.assertTrue(state["charge"]["refund_pending"])
        self.assertFalse(state["charge"]["refunded"])
        self.assertNotIn("record", calls)

    async def test_local_reconciliation_error_does_not_repeat_telegram_refund(self):
        handler, bot, state, calls = self._handler(record=RuntimeError("sqlite unavailable"))
        message = self.FakeMessage()

        await handler(message, bot)
        self.assertEqual(bot.calls, 1)
        self.assertTrue(state["charge"]["refund_pending"])
        self.assertFalse(state["charge"]["refunded"])
        self.assertIn("record", calls)
        self.assertTrue(any("Do not repeat /refund" in reply for reply in message.replies))

    async def test_refund_is_private_chat_admin_only_and_stars_only(self):
        handler, bot, _, _ = self._handler()
        group_message = self.FakeMessage(chat_type="group")
        await handler(group_message, bot)
        self.assertEqual(bot.calls, 0)
        self.assertTrue(any("private chat" in reply for reply in group_message.replies))

        unauthorized = self.FakeMessage(user_id=999)
        await handler(unauthorized, bot)
        self.assertEqual(bot.calls, 0)

        non_stars_handler, non_stars_bot, _, _ = self._handler(
            charge={
                "refunded": False,
                "refund_pending": False,
                "currency": "USD",
                "telegram_id": 777,
            }
        )
        non_stars = self.FakeMessage()
        await non_stars_handler(non_stars, non_stars_bot)
        self.assertEqual(non_stars_bot.calls, 0)
        self.assertTrue(any("Only Telegram Stars" in reply for reply in non_stars.replies))


if __name__ == "__main__":
    unittest.main()
