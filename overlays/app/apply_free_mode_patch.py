from __future__ import annotations

import ast
import sys
from pathlib import Path


REMOVED_COMMANDS = {
    "premium", "plans", "refund", "refundsync", "refundrelease",
    "charges", "paysupport", "support",
}
REMOVED_FUNCTIONS = {
    "_monthly_invoice_allowed", "send_pro_invoice", "premium", "plans_command",
    "pre_checkout", "pre_checkout_handler", "successful_payment",
    "refund_payment", "refund_sync", "refund_release", "list_recent_charges", "pay_support",
}


def _command_names(node: ast.AST) -> set[str]:
    names: set[str] = set()
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        if isinstance(child.func, ast.Name) and child.func.id == "Command":
            names.update(
                arg.value for arg in child.args
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
            )
    return names


def _is_paid_handler(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    if node.name == "free_plan_info":
        return False
    if node.name in REMOVED_FUNCTIONS:
        return True
    if any(_command_names(decorator) & REMOVED_COMMANDS for decorator in node.decorator_list):
        return True
    decorator_text = " ".join(ast.unparse(decorator) for decorator in node.decorator_list)
    return any(marker in decorator_text for marker in ("pre_checkout_query", "successful_payment"))


def patch_bot_source(source: str) -> str:
    """Remove purchase/refund handlers and keep a harmless command explaining free access."""
    tree = ast.parse(source)
    spans: list[tuple[int, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _is_paid_handler(node):
            first = min([node.lineno, *(decorator.lineno for decorator in node.decorator_list)])
            spans.append((first, node.end_lineno))

    if spans:
        lines = source.splitlines(keepends=True)
        removed: set[int] = set()
        for first, last in spans:
            removed.update(range(first - 1, last))
        source = "".join(line for index, line in enumerate(lines) if index not in removed)
        source = source.rstrip() + "\n"

    free_handler = '''    @dp.message(Command("premium", "plans"))
    async def free_plan_info(message: Message) -> None:
        await message.answer(
            "AntiScam Guardian is completely free. URL, TON wallet and Jetton scans are unlimited. "
            "There are no Pro plans, paid features, invoices, or in-bot payments."
        )

'''
    if "async def free_plan_info(" not in source:
        anchor = '    @dp.message(Command("help"))\n'
        if source.count(anchor) != 1:
            raise ValueError("Could not locate the single Telegram help handler")
        source = source.replace(anchor, free_handler + anchor, 1)

    source = source.replace(
        "Commands: /app, /scan, /wallet, /premium, /terms, /privacy, /paysupport. TON Connect is read-only in this version.",
        "Commands: /app, /scan, /wallet, /premium, /plans, /terms, /privacy. All scans are free and unlimited.",
    )

    ast.parse(source)
    forbidden = ("send_invoice(", "refund_star_payment(", "pre_checkout_query")
    found = [value for value in forbidden if value in source]
    if found:
        raise ValueError("Paid Telegram handler remains in bot source: " + ", ".join(found))
    if "settings.payments_mode" in source or "settings.stars_monthly_price" in source:
        raise ValueError("Bot still references paid configuration")
    return source


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("app/bot.py")
    source = path.read_text(encoding="utf-8")
    patched = patch_bot_source(source)
    path.write_text(patched, encoding="utf-8")
    print(f"PATCHED {path}")


if __name__ == "__main__":
    main()
