from __future__ import annotations

import ast
import unittest

from apply_bot_operator_patch import patch_bot_source


BOT_FIXTURE = '''from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from .config import get_settings
from .database import (
    TERMS_VERSION,
    accept_terms,
    activate_star_subscription,
    get_star_charge,
    recent_star_charges,
    has_accepted_terms,
    init_db,
    record_star_refund,
    upsert_user,
)

settings = get_settings()

async def send_pro_invoice(bot: Bot, chat_id: int, user_id: int) -> None:
    if settings.payments_mode != "telegram_stars" or settings.stars_monthly_price <= 0:
        await bot.send_message(
            chat_id,
            "Payments are disabled in this deployment. No funds are accepted. "
            "For digital services sold inside Telegram, the platform requires Telegram Stars (XTR). "
            "The bot owner may later be able to withdraw eligible Stars rewards as Toncoin through Telegram's supported flow.",
        )
        return
    if not has_accepted_terms(user_id):
        await bot.send_message(chat_id, "Read the Terms and Privacy Notice, then accept before purchasing Pro.")
        return
    await bot.send_invoice(
        chat_id=chat_id,
        title="AntiScam Guardian Pro — 30 days",
        description="Higher scan quota and extended scan history for 30 days.",
        payload="antiscam:pro:monthly:v1",
        currency="XTR",
        prices=[LabeledPrice(label="Pro access — 30 days", amount=settings.stars_monthly_price)],
        provider_token="",
    )

    @dp.pre_checkout_query()
    async def pre_checkout(query: PreCheckoutQuery) -> None:
        allowed = (
            settings.payments_mode == "telegram_stars"
            and settings.stars_monthly_price > 0
            and query.invoice_payload == "antiscam:pro:monthly:v1"
            and query.currency == "XTR"
            and query.total_amount == settings.stars_monthly_price
            and has_accepted_terms(query.from_user.id)
        )
        await query.answer(ok=allowed, error_message=None if allowed else "Not available")

    @dp.message(F.successful_payment)
    async def successful_payment(message: Message) -> None:
        payment = message.successful_payment
        if not payment or not message.from_user:
            return
        if (
            settings.payments_mode == "telegram_stars"
            and payment.currency == "XTR"
            and payment.invoice_payload == "antiscam:pro:monthly:v1"
            and payment.total_amount == settings.stars_monthly_price
            and has_accepted_terms(message.from_user.id)
        ):
            upsert_user(message.from_user.id, message.from_user.username)
            inserted = activate_star_subscription(
                payment.telegram_payment_charge_id,
                message.from_user.id,
                payment.total_amount,
                payment.currency,
                30,
            )
            if inserted:
                await message.answer("Payment confirmed. Pro access is active for 30 days.")
            else:
                await message.answer("This payment was already processed. Your previous Pro entitlement remains active.")

    @dp.message(Command("paysupport", "support"))
    async def pay_support(message: Message) -> None:
        await message.answer(
            "Billing support: send the payment date, approximate amount in Stars, and Telegram payment receipt details. "
            "Never send your wallet recovery phrase, private key, password, or authentication code."
        )

    @dp.message(Command("refund"))
    async def refund_payment(message: Message, bot: Bot) -> None:
        if not message.from_user or message.from_user.id not in settings.admin_telegram_ids:
            await message.answer("This command is restricted to the configured bot operator.")
            return
        parts = (message.text or "").split(maxsplit=1)
        if len(parts) != 2:
            await message.answer("Usage: /refund TELEGRAM_PAYMENT_CHARGE_ID")
            return
        charge_id = parts[1].strip()
        charge = get_star_charge(charge_id)
        if not charge:
            await message.answer("Charge ID not found in this bot's payment records.")
            return
        if charge["refunded"]:
            await message.answer("This charge is already recorded as refunded.")
            return
        if charge["currency"] != "XTR":
            await message.answer("Only Telegram Stars charges can be refunded by this command.")
            return
        try:
            await bot.refund_star_payment(user_id=charge["telegram_id"], telegram_payment_charge_id=charge_id)
            record_star_refund(charge_id)
            await message.answer("Telegram accepted the refund request. Verify its status in the bot's payment records.")
        except Exception:
            logger.exception("Telegram Stars refund failed")
            await message.answer("Refund request failed. Check the charge ID and Telegram Bot API status, then retry or contact support.")

    @dp.message(Command("help"))
    async def help_command(message: Message) -> None:
        await message.answer("Commands: /app, /scan, /wallet, /premium, /terms, /privacy, /paysupport. TON Connect is read-only in this version.")
'''


class BotOperatorPatchTests(unittest.TestCase):
    def test_payment_stays_blocked_without_refund_admin_and_support_contact(self):
        patched = patch_bot_source(BOT_FIXTURE)
        ast.parse(patched)
        invoice_gate = patched.split("async def send_pro_invoice", 1)[1].split("@dp.pre_checkout_query", 1)[0]
        self.assertIn("if not settings.admin_telegram_ids", invoice_gate)
        self.assertIn('os.getenv("SUPPORT_CONTACT", "").strip()', invoice_gate)
        pre_checkout = patched.split("async def pre_checkout", 1)[1].split("@dp.message(F.successful_payment)", 1)[0]
        self.assertIn("bool(settings.admin_telegram_ids)", pre_checkout)
        self.assertIn('bool(os.getenv("SUPPORT_CONTACT", "").strip())', pre_checkout)

    def test_successful_payment_is_delivered_even_if_billing_config_changes_after_checkout(self):
        patched = patch_bot_source(BOT_FIXTURE)
        handler = patched.split("@dp.message(F.successful_payment)", 1)[1].split(
            '@dp.message(Command("paysupport", "support"))', 1
        )[0]
        guard = handler.split("if (", 1)[1].split("):", 1)[0]
        self.assertNotIn("settings.payments_mode", guard)
        self.assertNotIn("settings.stars_monthly_price", guard)
        self.assertNotIn("has_accepted_terms", guard)
        self.assertIn('payment.currency == "XTR"', guard)
        self.assertIn('payment.invoice_payload == "antiscam:pro:monthly:v1"', guard)
        self.assertIn("payment.total_amount > 0", guard)
        self.assertIn("bool(payment.telegram_payment_charge_id)", guard)

    def test_pro_invoice_is_described_as_one_time_30_day_pass(self):
        patched = patch_bot_source(BOT_FIXTURE)
        self.assertIn('title="AntiScam Guardian Pro — 30-day pass"', patched)
        self.assertIn('description="30 days of Pro access. One-time purchase; does not auto-renew."', patched)

    def test_myid_only_discloses_callers_own_id_in_private_chat(self):
        patched = patch_bot_source(BOT_FIXTURE)
        handler = patched.split('@dp.message(Command("myid"))', 1)[1].split('@dp.message(Command("help"))', 1)[0]
        self.assertIn('message.chat.type != "private"', handler)
        self.assertIn("message.from_user.id", handler)
        self.assertIn("Your Telegram numeric ID:", handler)

    def test_paysupport_shows_configured_contact_or_safe_unconfigured_message(self):
        patched = patch_bot_source(BOT_FIXTURE)
        handler = patched.split('@dp.message(Command("paysupport", "support"))', 1)[1].split('@dp.message(Command("myid"))', 1)[0]
        self.assertIn('os.getenv("SUPPORT_CONTACT", "").strip()', handler)
        self.assertIn("Billing support:", handler)
        self.assertIn("support contact has not been configured", handler)
        self.assertIn("Never send your wallet recovery phrase", handler)

    def test_refund_handler_reserves_then_calls_telegram_then_reconciles(self):
        patched = patch_bot_source(BOT_FIXTURE)
        handler = patched.split('@dp.message(Command("refund"))', 1)[1].split('@dp.message(Command("refundsync"))', 1)[0]
        reserve = handler.index("begin_star_refund(charge_id)")
        remote = handler.index("bot.refund_star_payment")
        reconcile = handler.index("record_star_refund(charge_id)")
        self.assertLess(reserve, remote)
        self.assertLess(remote, reconcile)
        self.assertIn("pending marker retained", handler)
        self.assertIn("Do not repeat /refund", handler)

    def test_refund_recovery_commands_are_admin_only_and_require_explicit_confirmation(self):
        patched = patch_bot_source(BOT_FIXTURE)
        sync = patched.split('@dp.message(Command("refundsync"))', 1)[1].split('@dp.message(Command("refundrelease"))', 1)[0]
        release = patched.split('@dp.message(Command("refundrelease"))', 1)[1].split('@dp.message(Command("myid"))', 1)[0]
        for handler in (sync, release):
            self.assertIn("settings.admin_telegram_ids", handler)
            self.assertIn('message.chat.type != "private"', handler)
        self.assertIn("CONFIRMED_REFUNDED", sync)
        self.assertIn("CONFIRMED_NOT_REFUNDED", release)
        self.assertIn("does not issue a Telegram refund", sync)
        self.assertIn("does not cancel or issue a Telegram refund", release)

    def test_recent_charges_command_is_private_admin_only_and_bounded(self):
        patched = patch_bot_source(BOT_FIXTURE)
        handler = patched.split('@dp.message(Command("charges"))', 1)[1].split('@dp.message(Command("myid"))', 1)[0]
        self.assertIn('message.chat.type != "private"', handler)
        self.assertIn("settings.admin_telegram_ids", handler)
        self.assertIn("recent_star_charges(10)", handler)
        self.assertIn("row['charge_id']", handler)

    def test_patch_is_idempotent(self):
        once = patch_bot_source(BOT_FIXTURE)
        twice = patch_bot_source(once)
        self.assertEqual(twice, once)


if __name__ == "__main__":
    unittest.main()
