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
        'Commands: /app, /scan, /wallet, /premium, /terms, /privacy, /paysupport, /myid. TON Connect is read-only in this version.',
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
