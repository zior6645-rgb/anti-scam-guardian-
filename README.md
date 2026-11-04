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

See [RAILWAY-DEPLOY-fa.md](./RAILWAY-DEPLOY-fa.md). The service must run on an operator-approved hosting account with HTTPS, a persistent volume mounted at `/data`, exactly one replica, production Telegram authentication, and a freshly rotated bot token. Local Termux is a development/test environment, not a public production host.

The Docker image uses `python -m app.runtime` as its process supervisor. Do not override that command with a different supervisor script.

## Monetization status — disabled

The code contains an initial Telegram Stars path: `/premium` sends an XTR invoice, pre-checkout is validated, successful-payment updates are recorded idempotently, `/paysupport` is available, and an admin-only refund command calls the Stars refund API.

That code is **not yet approved for live billing**. Before enabling it, run Telegram's dedicated Stars test environment end-to-end and audit duplicate updates, invoice payload validation, charge reconciliation, refund failures, subscription extension/expiry/refund behavior, support handling, and backup/restore. Keep `PAYMENTS_MODE=disabled` and `STARS_MONTHLY_PRICE=0` until those tests and the legal/policy review pass.

Digital goods and services sold inside Telegram must be charged in Telegram Stars (`XTR`), not directly in TON. Telegram may route eligible developer rewards through Fragment, but its terms state that rewards can be unavailable in some countries or regulatory circumstances. Do not promise that Stars sales can always be withdrawn as TON or treated as guaranteed cash revenue.

## Before public launch

1. Revoke any bot token exposed outside a secret manager and create a fresh token in BotFather.
2. Deploy with HTTPS, persistent `/data`, one replica, `ALLOW_DEV_AUTH=false`, and a short Telegram init-data freshness window.
3. Complete the live deployment smoke test: `/health`, Mini App authentication, quota, URL, wallet, Jetton, and history.
4. Decide whether to configure a licensed/approved phishing-intelligence provider and document exactly what URL data is shared after consent.
5. Complete load/rate-limit/abuse tests, monitoring, backup and restore drills, operator support, and incident response.
6. Complete legal review of the operator identity, terms, privacy notice, retention/deletion policy, target markets, and hosting/payment eligibility.
7. Run the full Telegram Stars test lifecycle and independent security review before enabling billing.

This product provides limited risk indicators, not guaranteed scam detection or transaction safety. Do not market it as a security oracle.
