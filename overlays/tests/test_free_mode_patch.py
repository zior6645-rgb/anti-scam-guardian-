from __future__ import annotations

import unittest

from apply_free_mode_patch import patch_bot_source


BOT_FIXTURE = '''from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message

def _monthly_invoice_allowed(user_id: int) -> bool:
    return settings.payments_mode == "telegram_stars"

async def send_pro_invoice(bot: Bot, chat_id: int, user_id: int) -> None:
    await bot.send_invoice(chat_id=chat_id)

def build_dispatcher():
    dp = Dispatcher()

    @dp.message(Command("premium"))
    async def premium(message: Message, bot: Bot):
        await send_pro_invoice(bot, message.chat.id, message.from_user.id)

    @dp.message(Command("refund"))
    async def refund_payment(message: Message, bot: Bot):
        pass

    @dp.message(Command("paysupport"))
    async def pay_support(message: Message):
        pass

    @dp.pre_checkout_query()
    async def pre_checkout(query):
        pass

    @dp.message(F.successful_payment)
    async def successful_payment(message: Message):
        pass

    @dp.message(Command("help"))
    async def help_command(message: Message):
        await message.answer("Commands: /app, /scan, /wallet, /premium, /terms, /privacy, /paysupport. TON Connect is read-only in this version.")

    return dp
'''


class FreeModePatchTests(unittest.TestCase):
    def test_removes_purchase_refund_and_payment_update_handlers(self):
        patched = patch_bot_source(BOT_FIXTURE)
        self.assertNotIn("send_invoice(", patched)
        self.assertNotIn("refund_star_payment(", patched)
        self.assertNotIn("pre_checkout_query", patched)
        self.assertNotIn("successful_payment", patched)
        self.assertNotIn("settings.payments_mode", patched)
        self.assertNotIn("settings.stars_monthly_price", patched)
        self.assertNotIn("async def refund_payment", patched)
        self.assertNotIn("async def pay_support", patched)

    def test_keeps_a_free_unlimited_information_command(self):
        patched = patch_bot_source(BOT_FIXTURE)
        self.assertIn('Command("premium", "plans")', patched)
        self.assertIn("completely free", patched)
        self.assertIn("unlimited", patched)
        self.assertIn("All scans are free and unlimited.", patched)

    def test_patch_is_idempotent(self):
        once = patch_bot_source(BOT_FIXTURE)
        self.assertEqual(patch_bot_source(once), once)


if __name__ == "__main__":
    unittest.main()
