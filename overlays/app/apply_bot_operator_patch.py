from __future__ import annotations

import ast
import sys
from pathlib import Path


def _replace_once(source: str, old: str, new: str, label: str) -> str:
    if new in source:
        return source
    count = source.count(old)
    if count != 1:
        raise ValueError(f"Expected exactly one {label} anchor, found {count}")
    return source.replace(old, new, 1)


def patch_bot_source(source: str) -> str:
    """Patch the archived bot with safe operator setup and explicit pass wording."""
    if "import os\n" not in source:
        source = _replace_once(source, "import logging\n", "import logging\nimport os\n", "logging import")

    source = _replace_once(
        source,
        "    get_star_charge,\n",
        "    begin_star_refund,\n    cancel_star_refund,\n    get_star_charge,\n    recent_star_charges,\n",
        "refund coordination imports",
    )

    source = _replace_once(
        source,
        '        return\n    if not has_accepted_terms(user_id):',
        '''        return
    if not settings.admin_telegram_ids:
        await bot.send_message(
            chat_id,
            "Pro purchases are unavailable until the operator refund account is configured. No payment has been taken.",
        )
        return
    if not os.getenv("SUPPORT_CONTACT", "").strip():
        await bot.send_message(
            chat_id,
            "Pro purchases are unavailable until the billing support contact is published. No payment has been taken.",
        )
        return
    if not has_accepted_terms(user_id):''',
        "invoice preconditions",
    )

    source = _replace_once(
        source,
        '        title="AntiScam Guardian Pro — 30 days",',
        '        title="AntiScam Guardian Pro — 30-day pass",',
        "30-day invoice title",
    )
    source = _replace_once(
        source,
        '        provider_token="",',
        '        # Telegram Stars invoices intentionally use an empty provider token.\\n        provider_token="",  # nosec B106',
        "Telegram Stars empty provider token",
    )

    source = _replace_once(
        source,
        '        description="Higher scan quota and extended scan history for 30 days.",',
        '        description="30 days of Pro access. One-time purchase; does not auto-renew.",',
        "30-day invoice description",
    )

    source = _replace_once(
        source,
        '            and settings.stars_monthly_price > 0\n            and query.invoice_payload',
        '            and settings.stars_monthly_price > 0\n'
        '            and bool(settings.admin_telegram_ids)\n'
        '            and bool(os.getenv("SUPPORT_CONTACT", "").strip())\n'
        '            and query.invoice_payload',
        "pre-checkout operator preconditions",
    )

    # Telegram's successful_payment update means the charge has already happened.
    # A config switch or price change after pre-checkout must not strand a paid user.
    old_paid_payment_guard = '''        if (
            settings.payments_mode == "telegram_stars"
            and payment.currency == "XTR"
            and payment.invoice_payload == "antiscam:pro:monthly:v1"
            and payment.total_amount == settings.stars_monthly_price
            and has_accepted_terms(message.from_user.id)
        ):'''
    new_paid_payment_guard = '''        if (
            payment.currency == "XTR"
            and payment.invoice_payload == "antiscam:pro:monthly:v1"
            and payment.total_amount > 0
            and bool(payment.telegram_payment_charge_id)
        ):'''
    source = _replace_once(
        source,
        old_paid_payment_guard,
        new_paid_payment_guard,
        "successful payment delivery guard",
    )


    old_refund = '''    @dp.message(Command("refund"))
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
            await message.answer("Refund request failed. Check the charge ID and Telegram Bot API status, then retry or contact support.")'''
    new_refund = '''    @dp.message(Command("refund"))
    async def refund_payment(message: Message, bot: Bot) -> None:
        if message.chat.type != "private":
            await message.answer("Run refund administration commands in a private chat with this bot.")
            return
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
        if charge["refund_pending"]:
            await message.answer("A refund attempt is already pending reconciliation. Do not repeat /refund.")
            return
        if charge["currency"] != "XTR":
            await message.answer("Only Telegram Stars charges can be refunded by this command.")
            return
        if not begin_star_refund(charge_id):
            latest = get_star_charge(charge_id)
            if latest and latest["refunded"]:
                await message.answer("This charge is already recorded as refunded.")
            elif latest and latest["refund_pending"]:
                await message.answer("A refund attempt is already pending reconciliation. Do not repeat /refund.")
            else:
                await message.answer("Could not reserve this refund. No Telegram refund request was sent.")
            return
        try:
            accepted = await bot.refund_star_payment(
                user_id=charge["telegram_id"],
                telegram_payment_charge_id=charge_id,
            )
        except Exception:
            logger.exception("Telegram Stars refund outcome is uncertain; pending marker retained")
            await message.answer(
                "Telegram's refund result could not be confirmed. This charge is locked to prevent a duplicate refund. "
                "Check the Telegram payment status, then use /refundsync CHARGE_ID CONFIRMED_REFUNDED "
                "or /refundrelease CHARGE_ID CONFIRMED_NOT_REFUNDED. Do not retry /refund blindly."
            )
            return
        if not accepted:
            logger.error("Telegram did not confirm Stars refund for charge %s; pending marker retained", charge_id)
            await message.answer(
                "Telegram did not confirm the refund. The charge remains locked for review. "
                "Use /refundrelease only after verifying that no refund occurred."
            )
            return
        try:
            recorded = record_star_refund(charge_id)
        except Exception:
            logger.critical(
                "Telegram accepted Stars refund but local entitlement reconciliation failed for charge %s",
                charge_id,
                exc_info=True,
            )
            await message.answer(
                "Telegram accepted the refund, but the local Pro access record could not be synchronized. "
                "The charge is locked against duplicate refunds. Verify the Telegram refund, then use "
                "/refundsync CHARGE_ID CONFIRMED_REFUNDED. Do not repeat /refund."
            )
            return
        if not recorded:
            logger.critical("Telegram accepted Stars refund but local refund record was not completed for charge %s", charge_id)
            await message.answer(
                "Telegram accepted the refund, but the local refund record remains unresolved. "
                "Verify the Telegram refund, then use /refundsync CHARGE_ID CONFIRMED_REFUNDED."
            )
            return
        await message.answer("Telegram accepted the refund and the local Pro access period was reconciled.")

    @dp.message(Command("refundsync"))
    async def refund_sync(message: Message) -> None:
        if message.chat.type != "private":
            await message.answer("Run refund administration commands in a private chat with this bot.")
            return
        if not message.from_user or message.from_user.id not in settings.admin_telegram_ids:
            await message.answer("This command is restricted to the configured bot operator.")
            return
        parts = (message.text or "").split(maxsplit=2)
        if len(parts) != 3 or parts[2] != "CONFIRMED_REFUNDED":
            await message.answer("Usage: /refundsync TELEGRAM_PAYMENT_CHARGE_ID CONFIRMED_REFUNDED")
            return
        charge_id = parts[1].strip()
        charge = get_star_charge(charge_id)
        if not charge:
            await message.answer("Charge ID not found in this bot's payment records.")
            return
        if charge["refunded"]:
            await message.answer("The local record already shows this charge as refunded.")
            return
        if not charge["refund_pending"]:
            await message.answer("There is no pending refund to synchronize.")
            return
        try:
            recorded = record_star_refund(charge_id)
        except Exception:
            logger.exception("Manual Stars refund reconciliation failed for charge %s", charge_id)
            await message.answer("The local record could not be synchronized. Keep the charge pending and escalate it.")
            return
        if not recorded:
            await message.answer("The pending refund could not be synchronized. Keep the charge pending and escalate it.")
            return
        await message.answer(
            "The local Pro access and refund record are synchronized. This command does not issue a Telegram refund; "
            "use it only after independently confirming Telegram accepted the refund."
        )

    @dp.message(Command("refundrelease"))
    async def refund_release(message: Message) -> None:
        if message.chat.type != "private":
            await message.answer("Run refund administration commands in a private chat with this bot.")
            return
        if not message.from_user or message.from_user.id not in settings.admin_telegram_ids:
            await message.answer("This command is restricted to the configured bot operator.")
            return
        parts = (message.text or "").split(maxsplit=2)
        if len(parts) != 3 or parts[2] != "CONFIRMED_NOT_REFUNDED":
            await message.answer("Usage: /refundrelease TELEGRAM_PAYMENT_CHARGE_ID CONFIRMED_NOT_REFUNDED")
            return
        charge_id = parts[1].strip()
        charge = get_star_charge(charge_id)
        if not charge:
            await message.answer("Charge ID not found in this bot's payment records.")
            return
        if charge["refunded"]:
            await message.answer("This charge is already recorded as refunded and cannot be released.")
            return
        if not charge["refund_pending"]:
            await message.answer("There is no pending refund to release.")
            return
        try:
            released = cancel_star_refund(charge_id)
        except Exception:
            logger.exception("Pending Stars refund release failed for charge %s", charge_id)
            await message.answer("The pending refund could not be released. Keep it locked and escalate it.")
            return
        if not released:
            await message.answer("The pending refund could not be released. Recheck the charge before retrying.")
            return
        await message.answer(
            "The local pending marker was released. This command does not cancel or issue a Telegram refund; "
            "use it only after independently confirming Telegram did not refund this charge."
        )

    @dp.message(Command("charges"))
    async def list_recent_charges(message: Message) -> None:
        if message.chat.type != "private":
            await message.answer("Run payment administration commands in a private chat with this bot.")
            return
        if not message.from_user or message.from_user.id not in settings.admin_telegram_ids:
            await message.answer("This command is restricted to the configured bot operator.")
            return
        rows = recent_star_charges(10)
        if not rows:
            await message.answer("No successful Stars charges are recorded yet.")
            return
        lines = [
            f"{row['created_at']} | {row['amount']} {row['currency']} | user {row['telegram_id']} | {row['refund_status']}\\n{row['charge_id']}"
            for row in rows
        ]
        await message.answer("Latest Telegram Stars charges (newest first):\\n\\n" + "\\n\\n".join(lines))
'''
    source = _replace_once(source, old_refund, new_refund, "refund lifecycle handler")

    old_support = '''    @dp.message(Command("paysupport", "support"))
    async def pay_support(message: Message) -> None:
        await message.answer(
            "Billing support: send the payment date, approximate amount in Stars, and Telegram payment receipt details. "
            "Never send your wallet recovery phrase, private key, password, or authentication code."
        )
'''
    new_support = '''    @dp.message(Command("paysupport", "support"))
    async def pay_support(message: Message) -> None:
        support_contact = os.getenv("SUPPORT_CONTACT", "").strip()
        if support_contact:
            response = (
                f"Billing support: {support_contact}\\n"
                "Include the payment date and Telegram payment receipt details when contacting support. "
                "Never send your wallet recovery phrase, private key, password, or authentication code."
            )
        else:
            response = (
                "The billing support contact has not been configured. Real payments must remain disabled "
                "until the operator publishes a verified support contact. "
                "Never send your wallet recovery phrase, private key, password, or authentication code."
            )
        await message.answer(response)
'''
    source = _replace_once(source, old_support, new_support, "payment support handler")

    my_id_handler = '''    @dp.message(Command("myid"))
    async def my_id(message: Message) -> None:
        if message.chat.type != "private":
            await message.answer("Use /myid in a private chat with this bot.")
            return
        if not message.from_user:
            return
        await message.answer(
            f"Your Telegram numeric ID: {message.from_user.id}\\n"
            "Use this number to configure the bot operator's refund access."
        )

'''
    if '@dp.message(Command("myid"))' not in source:
        source = _replace_once(source, '    @dp.message(Command("help"))\n', my_id_handler + '    @dp.message(Command("help"))\n', "help handler insertion")

    source = _replace_once(
        source,
        'Commands: /app, /scan, /wallet, /premium, /terms, /privacy, /paysupport. TON Connect is read-only in this version.',
        'Commands: /app, /scan, /wallet, /premium, /terms, /privacy, /paysupport, /myid. Payment administration: /charges, /refund, /refundsync, /refundrelease (operator only). TON Connect is read-only in this version.',
        "help command list",
    )

    ast.parse(source)
    return source


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("app/bot.py")
    source = path.read_text(encoding="utf-8")
    patched = patch_bot_source(source)
    path.write_text(patched, encoding="utf-8")
    print(f"PATCHED {path}")


if __name__ == "__main__":
    main()
