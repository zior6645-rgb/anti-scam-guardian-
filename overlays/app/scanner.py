from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlparse

import httpx

from .config import get_settings
from .ton_address import normalize_ton_address


SHORTENER_DOMAINS = {
    "bit.ly",
    "t.co",
    "tinyurl.com",
    "is.gd",
    "cutt.ly",
    "rb.gy",
    "shorturl.at",
}
SUSPICIOUS_TERMS = {
    "airdrop",
    "claim",
    "connect-wallet",
    "wallet-connect",
    "seed",
    "recovery",
    "verify-wallet",
}


def scan_url(value: str) -> dict:
    text = value.strip()
    if len(text) > 2048:
        raise ValueError("URL is too long (maximum 2048 characters)")

    # Never reinterpret an explicit non-web URI scheme as an HTTPS hostname.
    if re.match(r"^[a-z][a-z0-9+.-]*:", text, flags=re.IGNORECASE) and not text.lower().startswith(
        ("http://", "https://")
    ):
        raise ValueError("Only http:// and https:// URLs are accepted")

    candidate = text if "://" in text else f"https://{text}"
    try:
        parsed = urlparse(candidate)
        host = parsed.hostname
    except ValueError as exc:
        raise ValueError("Enter a valid http:// or https:// URL") from exc

    if parsed.scheme not in {"http", "https"} or not host:
        raise ValueError("Enter a valid http:// or https:// URL")
    if parsed.username or parsed.password:
        raise ValueError("URLs containing embedded credentials are not accepted")

    host = host.rstrip(".").lower()
    flags: list[str] = []
    score = 0

    try:
        address = ipaddress.ip_address(host)
        flags.append("The hostname is a raw IP address")
        score += 30
        if not address.is_global:
            flags.append("The IP address is not globally routable")
            score += 40
    except ValueError:
        pass

    try:
        idna_host = host.encode("idna").decode("ascii").lower()
    except UnicodeError:
        idna_host = host
    if "xn--" in idna_host:
        flags.append("The hostname contains punycode (possible look-alike domain)")
        score += 25

    if host in SHORTENER_DOMAINS:
        flags.append("The URL uses a public link-shortening domain")
        score += 15

    if host.count(".") >= 4:
        flags.append("The hostname has an unusually deep subdomain structure")
        score += 10

    lowered = (host + parsed.path + "?" + parsed.query).lower()
    matching_terms = sorted(term for term in SUSPICIOUS_TERMS if term in lowered)
    if matching_terms:
        flags.append("The URL contains wallet/claim-related terms: " + ", ".join(matching_terms))
        score += 15

    if parsed.scheme == "http":
        flags.append("The URL does not use HTTPS")
        score += 10

    score = min(score, 100)
    level = "high" if score >= 50 else "caution" if score >= 20 else "no_obvious_flags"
    return {
        "kind": "url",
        "subject": host,
        "risk_level": level,
        "heuristic_score": score,
        "flags": flags,
        "method": "local_heuristics_only",
        "disclaimer": (
            "No obvious heuristic flags is not proof that a URL is safe. "
            "This is not a live threat-intelligence verdict."
        ),
    }


async def scan_ton_account(value: str, kind: str) -> dict:
    if kind not in {"wallet", "token"}:
        raise ValueError("Unsupported TON scan type")

    raw_address = normalize_ton_address(value)
    settings = get_settings()
    headers = {"Accept": "application/json"}
    if settings.tonapi_key:
        headers["Authorization"] = f"Bearer {settings.tonapi_key}"

    is_token = kind == "token"
    endpoint = "jettons" if is_token else "accounts"
    result: dict = {
        "kind": kind,
        "address": raw_address,
        "network": "TON",
        "risk_level": "insufficient_data",
        "method": "ton_address_validation",
        "flags": [],
        "disclaimer": (
            "Jetton metadata and provider verification are indicators, not a guarantee of safety."
            if is_token
            else "Address validity and public chain metadata do not establish that a wallet or contract is trustworthy."
        ),
    }

    try:
        timeout = httpx.Timeout(25.0, connect=15.0)
        async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
            response = await client.get(f"{settings.ton_api_base_url}/{endpoint}/{raw_address}")

        if response.status_code == 404:
            result["provider_status"] = 404
            result["flags"].append("TONAPI did not find this Jetton master or account")
            return result

        if response.status_code != 200:
            result["provider_status"] = response.status_code
            result["flags"].append("The public metadata provider did not return a usable result")
            return result

        body = response.json()
        if not isinstance(body, dict):
            result["flags"].append("The public metadata provider returned an unexpected response")
            return result

        if is_token:
            metadata = body.get("metadata")
            if not isinstance(metadata, dict):
                metadata = {}

            verification = str(body.get("verification") or "none").lower()
            if verification not in {"whitelist", "graylist", "blacklist"}:
                verification = "none"

            result.update(
                {
                    "method": "tonapi_jetton_master_metadata",
                    "jetton_name": metadata.get("name"),
                    "jetton_symbol": metadata.get("symbol"),
                    "jetton_decimals": metadata.get("decimals"),
                    "jetton_description": metadata.get("description"),
                    "jetton_image": metadata.get("image") or body.get("preview"),
                    "mintable": body.get("mintable"),
                    "total_supply": body.get("total_supply"),
                    "holders_count": body.get("holders_count"),
                    "jetton_verification": verification,
                }
            )

            admin = body.get("admin")
            if isinstance(admin, dict):
                result["admin_address"] = admin.get("address")

            provider_is_scam = body.get("is_scam")
            if provider_is_scam is not None:
                result["provider_is_scam"] = provider_is_scam

            if provider_is_scam is True or verification == "blacklist":
                result["risk_level"] = "high"
                result["flags"].append("TONAPI currently flags this Jetton master as a scam or blacklist")
            elif verification == "graylist":
                result["risk_level"] = "caution"
                result["flags"].append("TONAPI classifies this Jetton master as graylist")
            elif verification == "whitelist":
                result["risk_level"] = "not_assessed"
                result["flags"].append(
                    "TONAPI classifies this Jetton master as whitelist; this is not a safety guarantee"
                )
            else:
                result["risk_level"] = "insufficient_data"
                result["flags"].append("TONAPI has not classified this Jetton master")

            if provider_is_scam is False:
                result["flags"].append("TONAPI does not currently flag this Jetton master as a scam")
            elif provider_is_scam is None:
                result["flags"].append("TONAPI did not provide a scam-status indicator")

            result["flags"].append(
                "Token metadata and names can be imitated; verify the Jetton master address independently"
            )
        else:
            result.update(
                {
                    "method": "tonapi_public_account_metadata",
                    "account_status": body.get("status", "unknown"),
                    "balance_nanograms": body.get("balance"),
                    "last_activity": body.get("last_activity"),
                    "account_is_wallet": body.get("is_wallet"),
                    "account_name": body.get("name"),
                    "account_interfaces": body.get("interfaces"),
                }
            )

            provider_is_scam = body.get("is_scam")
            result["provider_is_scam"] = provider_is_scam

            if provider_is_scam is True:
                result["risk_level"] = "high"
                result["flags"].append("TONAPI currently flags this account as a scam")
            elif provider_is_scam is False:
                result["risk_level"] = "not_assessed"
                result["flags"].append("TONAPI does not currently flag this account as a scam")
            else:
                result["risk_level"] = "insufficient_data"
                result["flags"].append("TONAPI did not provide a scam-status indicator")

            result["flags"].append("Provider metadata is not a complete security verdict")

    except httpx.TimeoutException:
        result["flags"].append("TONAPI request timed out; retry later")
        result["provider_error"] = "timeout"
    except (httpx.HTTPError, ValueError, TypeError):
        result["flags"].append("On-chain metadata lookup is temporarily unavailable")
        result["provider_error"] = "provider_error"

    return result
