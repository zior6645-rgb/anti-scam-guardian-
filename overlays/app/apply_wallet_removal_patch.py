#!/usr/bin/env python3
"""Remove TON Connect server integration while preserving manual TON-address scans."""
from __future__ import annotations

from pathlib import Path
import re
import sys


TERMS = """AntiScam Guardian is a free screening tool for suspicious URLs, public TON wallet addresses and TON jetton contract addresses. Scans do not require a connected wallet, payment, deposit, transaction approval, seed phrase or private key. Users enter a URL or public address manually.

Results are limited automated indicators, not an antivirus product, smart-contract audit, financial service, investment advice or guarantee of safety. A low-risk or unlisted result does not prove that an item is safe. Verify independently before opening links or interacting with blockchain assets.

URL lookups may be sent to PhishTank only after the user explicitly opts in. Public TON wallet and jetton addresses may be sent to TONAPI to retrieve public blockchain metadata. Provider availability, coverage, rate limits and data may change. The service does not connect to wallets, sign transactions, custody assets, accept deposits or process payments."""


PRIVACY = """AntiScam Guardian processes Telegram numeric user IDs and usernames to authenticate users and provide scan history. It stores the scan type, a SHA-256 hash of the submitted input, limited scan output and timestamps. Raw submitted URLs and wallet/contract addresses are not stored as the scan input in the history database.

When a user explicitly opts in to an external phishing-feed lookup, the submitted URL is transmitted to PhishTank. Public TON wallet and jetton addresses are sent to TONAPI for blockchain metadata. The Mini App does not connect to wallets, request wallet permissions, initiate transactions, process payments or request seed phrases/private keys.

Before public launch, the operator must add its legal identity, contact details, retention period, lawful basis, processors, cross-border transfer details, deletion request process and applicable user rights. Do not submit confidential URLs or sensitive personal data for scanning."""


def patch_main(source: str) -> str:
    pattern = re.compile(
        r"\ndef build_tonconnect_manifest\(public_base_url: str\) -> dict:\n"
        r".*?\n\n@app\.get\(\"/health\"\)",
        re.DOTALL,
    )
    matches = list(pattern.finditer(source))
    if len(matches) == 1:
        source = pattern.sub('\n@app.get("/health")', source, count=1)
    elif len(matches) == 0 and "tonconnect-manifest" not in source.lower() and "build_tonconnect_manifest" not in source:
        pass
    else:
        raise RuntimeError("Could not uniquely locate the TON Connect manifest endpoint")

    source = source.replace(
        "from fastapi.responses import FileResponse, HTMLResponse, JSONResponse",
        "from fastapi.responses import FileResponse, HTMLResponse",
    )
    if "JSONResponse" in source or "tonconnect-manifest" in source.lower() or "build_tonconnect_manifest" in source:
        raise RuntimeError("TON Connect manifest code remains in app/main.py")

    old_index = '        return FileResponse(STATIC_DIR / "index.html")'
    new_index = (
        '        return FileResponse(\n'
        '            STATIC_DIR / "index.html",\n'
        '            headers={\n'
        '                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",\n'
        '                "Pragma": "no-cache",\n'
        '                "Expires": "0",\n'
        '            },\n'
        '        )'
    )
    if new_index not in source:
        if source.count(old_index) != 1:
            raise RuntimeError("Could not uniquely locate the Mini App index response for cache control")
        source = source.replace(old_index, new_index, 1)
    return source


def patch_config(source: str) -> str:
    source = source.replace(
        "    # This lets the Mini App and TON Connect manifest use Railway's HTTPS domain\n"
        "    # without requiring the operator to buy or manage a domain.\n",
        "    # Use Railway's HTTPS domain as the default public Mini App origin.\n",
    )
    source = source.replace(
        "    # A public domain can be generated after the first Railway deploy. Until then,\n"
        "    # the bot remains usable through commands and the Mini App button stays hidden.\n"
        "    # The manifest endpoint returns 503 until an HTTPS origin is configured.\n",
        "    # The bot remains usable through commands until a public HTTPS Mini App origin is configured.\n",
    )
    webapp_line = '    webapp_url = os.getenv("WEBAPP_URL", "").strip().rstrip("/") or public_base_url'
    cache_version = "20261122-ui-fix-1"
    if cache_version not in source:
        if source.count(webapp_line) != 1:
            raise RuntimeError("Could not uniquely locate WEBAPP_URL for Telegram WebView cache busting")
        source = source.replace(
            webapp_line,
            webapp_line + '\\n'
            '    if webapp_url:\\n'
            '        cache_separator = "&" if "?" in webapp_url else "?"\\n'
            f'        webapp_url = f"{{webapp_url}}{{cache_separator}}v={cache_version}"',
            1,
        )
    if "TON Connect" in source or "tonconnect" in source.lower() or "manifest endpoint" in source.lower():
        raise RuntimeError("TON Connect configuration documentation remains in app/config.py")
    return source


def patch_legal(source: str) -> str:
    source, terms_count = re.subn(
        r'^TERMS = """[\s\S]*?"""',
        'TERMS = """' + TERMS + '"""',
        source,
        count=1,
        flags=re.MULTILINE,
    )
    source, privacy_count = re.subn(
        r'^PRIVACY = """[\s\S]*?"""',
        'PRIVACY = """' + PRIVACY + '"""',
        source,
        count=1,
        flags=re.MULTILINE,
    )
    if terms_count != 1 or privacy_count != 1:
        raise RuntimeError("Could not uniquely update the app Terms and Privacy text")
    if "TON Connect" in source or "/paysupport" in source or "daily scan quota" in source.lower():
        raise RuntimeError("Legacy wallet-connection or paid-product language remains in app/legal.py")
    return source


def apply_wallet_removal(app_root: Path) -> bool:
    changed = False
    targets = {
        app_root / "main.py": patch_main,
        app_root / "config.py": patch_config,
        app_root / "legal.py": patch_legal,
    }
    for path, transform in targets.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        before = path.read_text(encoding="utf-8")
        after = transform(before)
        if after != before:
            path.write_text(after, encoding="utf-8")
            changed = True

    manifest = app_root / "static" / "tonconnect-manifest.json"
    if manifest.exists():
        manifest.unlink()
        changed = True

    if manifest.exists():
        raise RuntimeError("TON Connect manifest file still exists")
    return changed


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python apply_wallet_removal_patch.py APP_DIRECTORY")
    changed = apply_wallet_removal(Path(sys.argv[1]).resolve())
    print("PATCHED TON Connect backend integration" if changed else "TON Connect backend integration already removed")
