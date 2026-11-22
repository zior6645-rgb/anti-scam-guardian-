from __future__ import annotations

import ipaddress
import re
from difflib import SequenceMatcher
from urllib.parse import parse_qsl, quote, urlparse, urlunparse

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
SUSPICIOUS_TLDS = {
    "click", "country", "gq", "ml", "cf", "ga", "tk", "zip", "mov", "top", "work"
}
REDIRECT_PARAMETERS = {"redirect", "redirect_uri", "return", "return_to", "continue", "next", "target", "dest", "destination", "url"}
PHISHTANK_ENDPOINT = "https://checkurl.phishtank.com/checkurl/"
TONAPI_TIMEOUT = httpx.Timeout(25.0, connect=15.0)


def normalize_url_input(value: str) -> str:
    """Validate and canonicalize a user-supplied HTTP(S) URL without fetching it."""
    if not isinstance(value, str):
        raise ValueError("Enter a valid website URL")
    text = value.strip()
    if not text or len(text) > 2048:
        raise ValueError("Enter a URL between 1 and 2048 characters")
    if any(ord(ch) < 32 or ch.isspace() for ch in text) or "\\" in text:
        raise ValueError("URL contains whitespace or invalid control characters")
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

    if parsed.scheme.lower() not in {"http", "https"} or not hostname:
        raise ValueError("Enter a valid http:// or https:// URL")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("URLs containing embedded credentials are not accepted")
    if parsed.netloc.endswith(":"):
        raise ValueError("URL contains an invalid port")

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
        if len(labels) < 2:
            raise ValueError("A complete domain name is required; single-word hostnames are not accepted")
        if any(
            not label
            or len(label) > 63
            or label.startswith("-")
            or label.endswith("-")
            or not re.fullmatch(r"[a-z0-9-]+", label)
            for label in labels
        ):
            raise ValueError("Hostname contains invalid characters")
        tld = labels[-1]
        if len(tld) < 2 or not re.fullmatch(r"(?:[a-z]{2,}|xn--[a-z0-9-]{2,})", tld):
            raise ValueError("Hostname has an invalid top-level domain")

    netloc = f"[{ascii_host}]" if is_ip and ":" in ascii_host else ascii_host
    if port is not None:
        if not 1 <= port <= 65535:
            raise ValueError("URL port is outside the valid range")
        netloc += f":{port}"
    return urlunparse((parsed.scheme.lower(), netloc, parsed.path or "/", "", parsed.query, ""))


MULTI_LABEL_PUBLIC_SUFFIXES = {
    "ac.uk", "co.uk", "gov.uk", "ltd.uk", "me.uk", "net.uk", "org.uk", "plc.uk",
    "com.au", "net.au", "org.au", "edu.au", "gov.au",
    "co.nz", "net.nz", "org.nz", "govt.nz",
    "com.br", "net.br", "org.br",
    "com.cn", "net.cn", "org.cn", "gov.cn",
    "com.sg", "net.sg", "org.sg", "com.hk", "net.hk", "org.hk",
    "co.in", "firm.in", "net.in", "org.in", "gen.in", "ind.in",
    "co.jp", "ne.jp", "or.jp", "go.jp", "ac.jp",
    "co.kr", "or.kr", "go.kr", "com.mx", "com.tr", "com.tw",
    "com.ar", "com.pl", "com.ua", "com.my", "com.ph", "com.vn",
}

BRAND_DOMAINS = {
    "google": "google.com",
    "microsoft": "microsoft.com",
    "apple": "apple.com",
    "amazon": "amazon.com",
    "paypal": "paypal.com",
    "binance": "binance.com",
    "coinbase": "coinbase.com",
    "telegram": "telegram.org",
    "metamask": "metamask.io",
    "openai": "openai.com",
    "tether": "tether.to",
    "trustwallet": "trustwallet.com",
    "ledger": "ledger.com",
    "bybit": "bybit.com",
    "okx": "okx.com",
    "kraken": "kraken.com",
}


def get_registrable_domain(host: str) -> str:
    """Return an approximate registrable domain using common multi-label suffixes.

    This is intentionally not presented as a complete Public Suffix List parser.
    """
    host = host.strip(".").lower()
    try:
        ipaddress.ip_address(host)
        return host
    except ValueError:
        pass
    labels = host.split(".")
    if len(labels) < 2:
        return host
    last_two = ".".join(labels[-2:])
    suffix_size = 2 if last_two in MULTI_LABEL_PUBLIC_SUFFIXES else 1
    if len(labels) <= suffix_size:
        return host
    return ".".join(labels[-(suffix_size + 1):])


def _brand_mismatch(host: str, registrable_domain: str) -> tuple[str | None, bool]:
    labels = host.split(".")
    for brand, official_domain in BRAND_DOMAINS.items():
        for label in labels:
            compact = label.replace("-", "")
            if brand in compact and registrable_domain != official_domain:
                return brand, False

    base_label = registrable_domain.split(".")[0]
    normalized = base_label.replace("-", "")
    leet_normalized = normalized.translate(str.maketrans({"0": "o", "1": "l", "3": "e", "4": "a", "5": "s", "7": "t"}))
    for brand, official_domain in BRAND_DOMAINS.items():
        if registrable_domain == official_domain:
            continue
        if abs(len(leet_normalized) - len(brand)) <= 1 and SequenceMatcher(
            None, leet_normalized, brand
        ).ratio() >= 0.82:
            return brand, True
    return None, False



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
        flags.append("The hostname is a raw IP address rather than a named domain")
        score += 30
        registrable_domain = host
        subdomain_count = 0
    except ValueError:
        registrable_domain = get_registrable_domain(host)
        labels = host.split(".")
        subdomain_count = max(0, len(labels) - len(registrable_domain.split(".")))

    if "xn--" in host:
        flags.append("The hostname contains IDN punycode; inspect for visually confusable characters")
        score += 25

    if host in SHORTENER_DOMAINS:
        flags.append("The URL uses a public link-shortening domain, which hides the final destination")
        score += 15

    if subdomain_count >= 2:
        flags.append("The hostname has multiple nested subdomain labels")
        score += 10

    brand, is_lookalike = _brand_mismatch(host, registrable_domain)
    if brand:
        if is_lookalike:
            flags.append(
                f"The registrable domain resembles the brand '{brand}' but is not its official domain ({BRAND_DOMAINS[brand]})"
            )
            score += 40
        else:
            flags.append(
                f"The hostname uses the brand name '{brand}' outside its official domain ({BRAND_DOMAINS[brand]}); this can be a deceptive subdomain"
            )
            score += 45

    lowered = (host + parsed.path + "?" + parsed.query).lower()
    searchable = re.sub(r"[^a-z0-9]+", " ", lowered)
    matching_terms = sorted(
        term for term in SUSPICIOUS_TERMS
        if term.replace("-", " ") in searchable
    )
    if matching_terms:
        flags.append("The URL contains wallet/claim-related terms: " + ", ".join(matching_terms))
        score += 15

    labels = host.split(".")
    if len(host) >= 55:
        flags.append("The hostname is unusually long")
        score += 10
    if host.count("-") >= 3:
        flags.append("The hostname contains an unusually high number of hyphens")
        score += 10
    if any(re.search(r"\d{4,}", label) for label in labels):
        flags.append("The hostname contains a long numeric sequence")
        score += 10

    tld = labels[-1] if labels else ""
    if tld in SUSPICIOUS_TLDS:
        flags.append(f"The URL uses a TLD that can be abused in phishing campaigns: .{tld}")
        score += 20

    redirect_keys = sorted(
        key.lower()
        for key, _value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() in REDIRECT_PARAMETERS
    )
    if redirect_keys:
        flags.append("The URL contains redirect-style parameters: " + ", ".join(redirect_keys))
        score += 10

    if parsed.port is not None and parsed.port not in {80, 443}:
        flags.append("The URL uses a non-standard web port")
        score += 10
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
    # A non-empty indicator list must never be paired with a clean/no-obvious-flags verdict.
    if intelligence["status"] == "confirmed_phishing" or score >= 50:
        level = "high"
    elif intelligence["status"] == "listed_not_confirmed" or flags:
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
        feed_note = "PhishTank did not list this URL in the lookup performed; this is not proof of safety."
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
        "hostname": host,
        "registrable_domain": registrable_domain,
        "subdomain_count": subdomain_count,
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
            "Heuristic scores are rule-based indicators, not probabilities. "
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
