# AntiScam Guardian

Telegram-first TON security assistant. This repository contains a release candidate for a limited screening product; it is not an independently audited security service.

## Current capabilities

- Telegram Mini App and bot runtime, with a single long-polling bot process.
- URL syntax checks and local heuristic indicators.
- Optional PhishTank lookup only after an explicit per-scan user opt-in and only when an operator-supplied application key is configured.
- TON account metadata through TonAPI, including the provider's current `is_scam` indicator when available.
- TON Jetton master metadata through TonAPI, including name, symbol, decimals, supply, mintability, holder count, and provider verification classification.
- The Mini App displays available public account and Jetton metadata. Metadata fields are treated as untrusted display strings and inserted through DOM text nodes.
- Per-user daily quota, recent scan history, Telegram Mini App `initData` authentication, and a persistent SQLite database.
- Docker image build and CI verification for the same source archive and reviewed overlays.

## What a scan does not do

- URL checks do not fetch or execute the submitted website. Local heuristics are not a live threat-intelligence verdict.
- PhishTank is one source, not a complete phishing or malware feed. External lookup is only performed after consent; URL query strings may contain secrets.
- TonAPI results are public provider metadata, not a wallet reputation audit, token economics review, liquidity analysis, honeypot test, bytecode audit, or transaction simulation.
- A whitelist or a false `is_scam` value is not proof of safety. Provider classifications can change, and scams may be missed.
- Never request seed phrases, private keys, wallet passwords, transfers, or transaction approval to perform a scan.

## Deployment

See [RAILWAY-DEPLOY-fa.md](./RAILWAY-DEPLOY-fa.md). The live Railway service is currently deployed from `commercial-readiness-026`, uses HTTPS and a persistent volume mounted at `/data`, and runs one bot poller. Hosting-country eligibility and the final production-authentication values must still be verified by the operator. Keep the bot token only in the host's secret store; if it is ever exposed, revoke and rotate it. Local Termux is a development/test environment, not a public production host.

The Docker image uses `python -m app.runtime` as its process supervisor. Do not override that command with a different supervisor script.

## Current deployment snapshot — 2026-11-05

- Railway service `anti-scam-guardian-bot` is online on branch `commercial-readiness-026` at commit `40cbe06a`.
- The persistent `/data` volume and HTTPS Railway domain are configured; the current service health check and Telegram polling start were observed in deployment logs.
- `ADMIN_TELEGRAM_IDS` and `SUPPORT_CONTACT` are configured. `/paysupport` was manually checked and returned the configured support handle.
- Production billing remains disabled: `PAYMENTS_MODE=disabled` and `STARS_MONTHLY_PRICE=0`.
- The live Stars checkout and refund lifecycle has not been tested end-to-end in Telegram's test environment. PR #4 is a separate, draft-only hardening branch and must not be treated as deployed.

## Monetization status — disabled

The code contains an initial Telegram Stars path: `/premium` sends an XTR invoice, pre-checkout is validated, successful-payment updates are recorded idempotently, `/paysupport` is available, and an admin-only refund command calls the Stars refund API. The deployed refund handler still needs stronger recovery for the case where Telegram accepts a refund but the local database update fails. Draft PR [#4](https://github.com/zior6645-rgb/anti-scam-guardian-/pull/4) adds a persistent pending-refund marker, duplicate-call protection, and admin reconciliation commands; it is not merged or deployed.

That code is **not yet approved for live billing**. The current offer is a **one-time 30-day pass** and does not auto-renew. Before enabling it, run Telegram's dedicated Stars test environment end-to-end and audit duplicate updates, invoice payload validation, charge reconciliation, refund failures, entitlement expiry/refund behavior, support handling, and backup/restore. The bot must have a configured refund administrator (`ADMIN_TELEGRAM_IDS`) and a published support contact (`SUPPORT_CONTACT`) before it may issue or approve a Stars invoice. Keep `PAYMENTS_MODE=disabled` and `STARS_MONTHLY_PRICE=0` until those tests and the legal/policy review pass.

Digital goods and services sold inside Telegram must be charged in Telegram Stars (`XTR`), not directly in TON or USDT. Do not add a wallet deposit flow, manual transaction confirmation, or on-chain crediting to unlock Pro access or increase the Mini App scan quota. TON Connect is a wallet connection protocol for permitted TON interactions; it is not a substitute checkout method for this in-Telegram digital service. Telegram may route eligible developer rewards through Fragment, but its terms state that rewards can be unavailable in some countries or regulatory circumstances. Do not promise that Stars sales can always be withdrawn as TON or treated as guaranteed cash revenue.

## Before public launch

1. Keep the active bot token only in Railway's secret store. If it is exposed outside a secret manager, revoke it and issue a fresh token in BotFather.
2. Deploy with HTTPS, persistent `/data`, one replica, `ALLOW_DEV_AUTH=false`, and a short Telegram init-data freshness window.
3. Complete the live deployment smoke test: `/health`, Mini App authentication, quota, URL, wallet, Jetton, and history.
4. Decide whether to configure a licensed/approved phishing-intelligence provider and document exactly what URL data is shared after consent.
5. Complete load/rate-limit/abuse tests, monitoring, backup and restore drills, operator support, and incident response.
6. Complete legal review of the operator identity, terms, privacy notice, retention/deletion policy, target markets, and hosting/payment eligibility.
7. Run the full Telegram Stars test lifecycle and independent security review before enabling billing.

This product provides limited risk indicators, not guaranteed scam detection or transaction safety. Do not market it as a security oracle.
