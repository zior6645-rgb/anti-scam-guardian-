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

See [RAILWAY-DEPLOY-fa.md](./RAILWAY-DEPLOY-fa.md). The live Railway service is currently deployed from `commercial-readiness-026`, uses HTTPS and a persistent volume mounted at `/data`, and runs one bot poller. Production settings were explicitly set to `ALLOW_DEV_AUTH=false` and `TELEGRAM_INITDATA_MAX_AGE_SECONDS=600`; the OAuth connection hides the variable values on read-back. Hosting-country eligibility still needs owner/legal verification. Keep the bot token only in the host's secret store; if it is ever exposed, revoke and rotate it. Local Termux is a development/test environment, not a public production host.

The Docker image uses `python -m app.runtime` as its process supervisor. Do not override that command with a different supervisor script.

## Current deployment snapshot — 2026-11-05

- Railway service `anti-scam-guardian-bot` is online on branch `commercial-readiness-026`. Check the latest Railway deployment record for the exact running commit.
- The persistent `/data` volume and HTTPS Railway domain are configured; the current service health check and Telegram polling start were observed in deployment logs.
- `ADMIN_TELEGRAM_IDS` and `SUPPORT_CONTACT` variables are present. `/paysupport` was manually checked and displayed the configured handle, but the support inbox's real-world responsiveness has not been independently verified.
- Production billing remains disabled: `PAYMENTS_MODE=disabled` and `STARS_MONTHLY_PRICE=0`.
- The live Stars checkout and refund lifecycle has not been tested end-to-end in Telegram's test environment. PR #4's refund hardening, PR #5's payment mock tests, and PR #6's Telegram Mini App authentication regression suite are merged and deployed. None enables production billing.

## Monetization status — disabled

The code contains an initial Telegram Stars path: `/premium` sends an XTR invoice, pre-checkout is validated, successful-payment updates are recorded idempotently, `/paysupport` is available, and an admin-only refund command calls the Stars refund API. PR [#4](https://github.com/zior6645-rgb/anti-scam-guardian-/pull/4) hardens refund reconciliation and duplicate-call protection. PR [#5](https://github.com/zior6645-rgb/anti-scam-guardian-/pull/5) adds mock payment/refund lifecycle tests. PR [#6](https://github.com/zior6645-rgb/anti-scam-guardian-/pull/6) adds HMAC, tampering, expiry, duplicate-field and production-config regression tests for Telegram Mini App authentication. The merged production branch passed [GitHub Actions Run #143](https://github.com/zior6645-rgb/anti-scam-guardian-/actions/runs/42051447150): 88 Python tests, 2 JavaScript tests, the Mini App build, and the Docker build. These are code-level tests, not live Telegram payment confirmation. Billing remains disabled until official Telegram test-environment and legal checks are complete.

That code is **not yet approved for live billing**. The current offer is a **one-time 30-day pass** and does not auto-renew. Before enabling it, run Telegram's dedicated Stars test environment end-to-end and audit duplicate updates, invoice payload validation, charge reconciliation, refund failures, entitlement expiry/refund behavior, support handling, and backup/restore. The bot must have a configured refund administrator (`ADMIN_TELEGRAM_IDS`) and a published support contact (`SUPPORT_CONTACT`) before it may issue or approve a Stars invoice. Keep `PAYMENTS_MODE=disabled` and `STARS_MONTHLY_PRICE=0` until those tests and the legal/policy review pass.

Digital goods and services sold inside Telegram must be charged in Telegram Stars (`XTR`), not directly in TON or USDT. Do not add a wallet deposit flow, manual transaction confirmation, or on-chain crediting to unlock Pro access or increase the Mini App scan quota. TON Connect is a wallet connection protocol for permitted TON interactions; it is not a substitute checkout method for this in-Telegram digital service. Telegram may route eligible developer rewards through Fragment, but its terms state that rewards can be unavailable in some countries or regulatory circumstances. Do not promise that Stars sales can always be withdrawn as TON or treated as guaranteed cash revenue.

## Before public launch

1. Keep the active bot token only in Railway's secret store. If it is exposed outside a secret manager, revoke it and issue a fresh token in BotFather.
2. Deploy with HTTPS, persistent `/data`, one replica, `ALLOW_DEV_AUTH=false`, and `TELEGRAM_INITDATA_MAX_AGE_SECONDS=600`; production values were set through Railway. The actual Mini App HMAC validation logic has automated regression coverage.
3. Complete the live deployment smoke test: `/health`, Mini App authentication, quota, URL, wallet, Jetton, and history.
4. Decide whether to configure a licensed/approved phishing-intelligence provider and document exactly what URL data is shared after consent.
5. In Railway, open the service's **Backups** tab and enable the **Daily** volume backup schedule, then verify a backup appears and run a documented restore drill. Add an independent off-volume backup if cross-volume disaster recovery is required. Complete load/rate-limit/abuse tests, support-response verification, and incident response.
6. Complete legal review of the operator identity, terms, privacy notice, retention/deletion policy, target markets, and hosting/payment eligibility.
7. Run the full Telegram Stars test lifecycle and independent security review before enabling billing.

This product provides limited risk indicators, not guaranteed scam detection or transaction safety. Do not market it as a security oracle.
