from __future__ import annotations

import ipaddress
import re
from urllib.parse import quote, urlparse, urlunparse

import httpx

from .config import get_settings
from .ton_address import normalize_ton_address

SHORTENER_DOMAINS = {
    "bit.ly", "t.co", "tinyurl.com", "is.gd", "cutt.ly", "rb.gy", "shorturl.at"
}
SUSPICIOUS_TERMS = {
    "airdrop", "claim", "connect-wallet", "wallet-connect",
    "seed", "recovery", "verify-wallet"
}
PHISHTANK_ENDPOINT = "https://checkurl.phishtank.com/checkurl/"
TONAPI_TIMEOUT = httpx.Timeout(25.0, connect=15.0)


def normalize_url_input(value: str) -> str:
    text = value.strip()
    if not text or len(text) > 2048:
        raise ValueError("Enter a URL between 1 and 2048 characters")
    if any(ord(ch) < 32 for ch in text):
        raise ValueError("URL contains control characters")
    if re.match(r"^[a-z][a-z0-9+.-]*:", text, flags=re.IGNORECASE) and not text.lower().startswith(
        ("http://", "https://")
    ):
        raise ValueError("Only http:// and https:// URLs are accepted")

    candidate = text if "://" in text else f"https://{text}"
    try:
        parsed = urlparse(candidate)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Enter a valid http:// or https:// URL") from exc

    if parsed.scheme not in {"http", "https"} or not hostname:
        raise ValueError("Enter a valid http:// or https:// URL")
    if parsed.username or parsed.password:
        raise ValueError("URLs containing embedded credentials are not accepted")

    host = hostname.rstrip(".").lower()
    if not host or host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        raise ValueError("Local or invalid hostnames are not accepted")

    is_ip = False
    try:
        ip = ipaddress.ip_address(host)
        is_ip = True
        if not ip.is_global:
            raise ValueError("Private or reserved IP addresses are not accepted")
        ascii_host = ip.compressed
    except ValueError as exc:
        if str(exc) == "Private or reserved IP addresses are not accepted":
            raise
        try:
            ascii_host = host.encode("idna").decode("ascii").lower()
        except UnicodeError as idna_exc:
            raise ValueError("Hostname is invalid") from idna_exc
        if len(ascii_host) > 253:
            raise ValueError("Hostname is too long")
        labels = ascii_host.split(".")
        if any(
            not label or len(label) > 63 or label.startswith("-")
            or label.endswith("-") or not re.fullmatch(r"[a-z0-9-]+", label)
            for label in labels
        ):
            raise ValueError("Hostname contains invalid characters")

    netloc = f"[{ascii_host}]" if is_ip and ":" in ascii_host else ascii_host
    if port is not None:
        netloc += f":{port}"
    return urlunparse((parsed.scheme.lower(), netloc, parsed.path or "/", "", parsed.query, ""))


async def _check_phishtank(url: str, app_key: str) -> dict:
    data = {"url": url, "format": "json", "app_key": app_key}
    headers = {
        "User-Agent": "AntiScamGuardian/0.2.5 (phishing URL checker)",
        "Accept": "application/json",
    }
    try:
        timeout = httpx.Timeout(8.0, connect=4.0)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            response = await client.post(PHISHTANK_ENDPOINT, data=data, headers=headers)
        if response.status_code == 509:
            return {"provider": "PhishTank", "status": "rate_limited"}
        response.raise_for_status()
        body = response.json()
        result = body.get("results", {}) if isinstance(body, dict) else {}
        if isinstance(result, list):
            result = result[0] if result else {}
        if not isinstance(result, dict):
            result = {}

        truthy = (True, "true", "y", "yes", "1", 1)
        in_database = result.get("in_database") in truthy
        verified = result.get("verified") in truthy
        valid = result.get("valid") in truthy
        if in_database and verified and valid:
            status = "confirmed_phishing"
        elif in_database:
            status = "listed_not_confirmed"
        else:
            status = "not_listed"
        return {
            "provider": "PhishTank",
            "status": status,
            "phish_id": result.get("phish_id"),
            "detail_url": result.get("phish_detail_page"),
            "verified_at": result.get("verified_at"),
        }
    except (httpx.HTTPError, ValueError, TypeError):
        return {"provider": "PhishTank", "status": "unavailable"}


async def scan_url(value: str, *, share_with_phishtank: bool = False) -> dict:
    url = normalize_url_input(value)
    parsed = urlparse(url)
    host = parsed.hostname or ""
    flags: list[str] = []
    score = 0

    try:
        ipaddress.ip_address(host)
        flags.append("The hostname is a raw IP address")
        score += 30
    except ValueError:
        pass
    if "xn--" in host:
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

    settings = get_settings()
    intelligence = {
        "provider": "PhishTank",
        "status": "not_configured" if not settings.phishtank_app_key else "not_checked_no_consent",
    }
    if settings.phishtank_app_key and share_with_phishtank:
        intelligence = await _check_phishtank(url, settings.phishtank_app_key)
        if intelligence["status"] == "confirmed_phishing":
            flags.append("PhishTank lists this URL as a verified and currently valid phishing URL")
            score = 100
        elif intelligence["status"] == "listed_not_confirmed":
            flags.append("PhishTank contains a listing for this URL, but it is not confirmed as currently valid")
            score = max(score, 35)

    score = min(score, 100)
    if intelligence["status"] == "confirmed_phishing" or score >= 50:
        level = "high"
    elif intelligence["status"] == "listed_not_confirmed" or score >= 20:
        level = "caution"
    else:
        level = "no_obvious_flags"
    method = (
        "heuristics_plus_phishtank"
        if intelligence["status"] not in {"not_configured", "not_checked_no_consent", "unavailable", "rate_limited"}
        else "local_heuristics_only"
    )
    feed_status = intelligence["status"]
    if feed_status == "not_configured":
        feed_note = "PhishTank is not configured; this scan used local heuristics only."
    elif feed_status == "not_checked_no_consent":
        feed_note = "PhishTank was not queried because external sharing was not approved."
    elif feed_status == "not_listed":
        feed_note = "PhishTank did not list this URL in the lookup performed."
    elif feed_status == "listed_not_confirmed":
        feed_note = "PhishTank returned a listing that is not confirmed as currently valid."
    elif feed_status == "confirmed_phishing":
        feed_note = "PhishTank reports this URL as verified, currently valid phishing."
    elif feed_status == "rate_limited":
        feed_note = "PhishTank rate-limited the lookup; no feed result is available."
    else:
        feed_note = "PhishTank lookup was unavailable or inconclusive."

    return {
        "kind": "url",
        "subject": host,
        "risk_level": level,
        "heuristic_score": score,
        "flags": flags,
        "method": method,
        "threat_intelligence": intelligence,
        "external_lookup_shared": bool(
            settings.phishtank_app_key and share_with_phishtank
            and intelligence["status"] not in {"unavailable", "rate_limited"}
        ),
        "disclaimer": (
            f"{feed_note} "
            "A lack of detected indicators does not prove safety. "
            "This is a limited screening result, not a security audit."
        ),
    }


async def scan_ton_account(value: str) -> dict:
    raw_address = normalize_ton_address(value)
    settings = get_settings()
    headers = {"Accept": "application/json"}
    if settings.tonapi_key:
        headers["Authorization"] = f"Bearer {settings.tonapi_key}"

    result: dict = {
        "kind": "wallet",
        "address": raw_address,
        "network": "TON",
        "risk_level": "insufficient_data",
        "method": "tonapi_account_metadata",
        "flags": [],
        "disclaimer": (
            "Public account metadata is not a wallet reputation verdict and does not establish "
            "that an address is trustworthy."
        ),
    }
    try:
        path_address = quote(raw_address, safe="")
        async with httpx.AsyncClient(timeout=TONAPI_TIMEOUT, headers=headers) as client:
            response = await client.get(f"{settings.ton_api_base_url}/accounts/{path_address}")

        if response.status_code == 200:
            body = response.json()
            if not isinstance(body, dict):
                raise ValueError("Unexpected account response")
            result.update({
                "account_status": body.get("status", "unknown"),
                "last_activity": body.get("last_activity"),
                "balance_nanograms": body.get("balance"),
                "account_name": body.get("name"),
                "account_is_wallet": body.get("is_wallet"),
                "account_interfaces": body.get("interfaces"),
            })
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
            result["flags"].append("Public account metadata is not a complete security verdict")
        elif response.status_code == 404:
            result["account_status"] = "not_found_or_not_indexed"
            result["provider_status"] = 404
            result["flags"].append("TONAPI did not find this account; it may be inactive or not indexed")
        elif response.status_code == 429:
            result["provider_status"] = "rate_limited"
            result["flags"].append("TONAPI rate limit reached; no account verdict is available")
        else:
            result["provider_status"] = response.status_code
            result["flags"].append("TONAPI did not return a usable account result")
    except httpx.TimeoutException:
        result["provider_status"] = "timeout"
        result["flags"].append("TONAPI account lookup timed out; retry later")
    except (httpx.HTTPError, ValueError, TypeError):
        result["provider_status"] = "unavailable"
        result["flags"].append("TONAPI account lookup is temporarily unavailable")
    return result


async def scan_ton_jetton(value: str) -> dict:
    """Fetch Jetton master metadata through TonAPI's /v2/jettons/{account_id} endpoint."""
    raw_address = normalize_ton_address(value)
    settings = get_settings()
    headers = {"Accept": "application/json"}
    if settings.tonapi_key:
        headers["Authorization"] = f"Bearer {settings.tonapi_key}"

    result: dict = {
        "kind": "token",
        "address": raw_address,
        "network": "TON",
        "risk_level": "insufficient_data",
        "method": "tonapi_jetton_metadata",
        "flags": [],
        "disclaimer": (
            "TONAPI verification metadata is one signal only. This is not a contract audit, "
            "liquidity check, or guarantee against malicious behavior."
        ),
    }
    try:
        path_address = quote(raw_address, safe="")
        async with httpx.AsyncClient(timeout=TONAPI_TIMEOUT, headers=headers) as client:
            response = await client.get(f"{settings.ton_api_base_url}/jettons/{path_address}")

        if response.status_code == 200:
            body = response.json()
            if not isinstance(body, dict):
                raise ValueError("Unexpected Jetton response")
            metadata = body.get("metadata") or {}
            if not isinstance(metadata, dict):
                metadata = {}
            verification = str(body.get("verification") or "unknown").lower()
            result.update({
                "token_name": metadata.get("name"),
                "token_symbol": metadata.get("symbol"),
                "decimals": metadata.get("decimals"),
                "description": metadata.get("description"),
                "image": metadata.get("image") or body.get("preview"),
                "total_supply": body.get("total_supply"),
                "mintable": body.get("mintable"),
                "holders_count": body.get("holders_count"),
                "verification": verification,
            })
            provider_is_scam = body.get("is_scam")
            if provider_is_scam is not None:
                result["provider_is_scam"] = provider_is_scam

            if provider_is_scam is True or verification == "blacklist":
                result["risk_level"] = "high"
                result["flags"].append("TONAPI marks this Jetton as blacklisted or scam-related")
            elif verification in {"greylist", "graylist"}:
                result["risk_level"] = "caution"
                result["flags"].append("TONAPI marks this Jetton as greylisted; verify independently")
            elif verification == "whitelist":
                result["risk_level"] = "provider_whitelisted"
                result["flags"].append(
                    "TONAPI reports a whitelist verification status; this is not a safety guarantee"
                )
            else:
                result["risk_level"] = "not_verified"
                result["flags"].append("No positive TONAPI verification status was returned")

            if provider_is_scam is False:
                result["flags"].append("TONAPI does not currently flag this Jetton as a scam")
            result["flags"].append(
                "Jetton names and metadata can be imitated; verify the master address independently"
            )
        elif response.status_code == 404:
            result["provider_status"] = 404
            result["flags"].append("TONAPI did not find indexed Jetton metadata for this address")
        elif response.status_code == 429:
            result["provider_status"] = "rate_limited"
            result["flags"].append("TONAPI rate limit reached; token metadata is unavailable")
        else:
            result["provider_status"] = response.status_code
            result["flags"].append("TONAPI did not return usable Jetton metadata")
    except httpx.TimeoutException:
        result["provider_status"] = "timeout"
        result["flags"].append("TONAPI Jetton lookup timed out; retry later")
    except (httpx.HTTPError, ValueError, TypeError):
        result["provider_status"] = "unavailable"
        result["flags"].append("TONAPI Jetton lookup is temporarily unavailable")
    return result
