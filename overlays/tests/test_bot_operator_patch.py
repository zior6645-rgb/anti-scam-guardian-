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
            await message.answer("Payment confirmed. Pro access is active for 30 days.")

    @dp.message(Command("paysupport", "support"))
    async def pay_support(message: Message) -> None:
        await message.answer(
            "Billing support: send the payment date, approximate amount in Stars, and Telegram payment receipt details. "
            "Never send your wallet recovery phrase, private key, password, or authentication code."
        )

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

    def test_patch_is_idempotent(self):
        once = patch_bot_source(BOT_FIXTURE)
        twice = patch_bot_source(once)
        self.assertEqual(twice, once)


if __name__ == "__main__":
    unittest.main()
