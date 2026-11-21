# Free product readiness — AntiScam Guardian

Last updated: 2026-11-22
Working branch: free-unlimited-20261122

## Product decision

The product is free for every user. There is no Pro tier, paid feature, daily scan quota, history quota, invoice, subscription, checkout, refund handler or in-bot payment path.

The API returns a Free account with unlimited scans. The Mini App shows the same free/unlimited state before and after each scan. Scan history has no Free/Pro item limit.

Unlimited is an application policy, not an unlimited hosting or provider guarantee. Railway capacity, database size, Telegram, TonAPI and optional PhishTank rate limits still apply.

## Implementation scope

- Force FREE_SCANS_PER_DAY to zero internally; zero means unlimited.
- Remove paid configuration fields from the application settings.
- Remove scan quota rejection from the database reservation path.
- Remove the history item cap from the history query.
- Remove the Telegram purchase, pre-checkout, successful-payment, refund, billing-support and payment-administration handlers.
- Keep /premium and /plans as informational commands that state the product is free.
- Remove Pro labels and counters from the Mini App.
- Keep existing database records and encrypted backup infrastructure; do not delete old records during this product change.

## Verification required

- Source reconstruction and every production overlay must be idempotent.
- Backend tests must pass, including API tests that create more than five scans and retrieve more than five history items.
- Bot tests must prove no invoice, pre-checkout or refund handler remains.
- JavaScript tests and production Mini App build must pass.
- Docker image build must pass.
- Confirm the Railway service remains unchanged until the owner explicitly approves deployment.

## Deployment status

This branch is a change candidate. Passing GitHub Actions is required before deployment. No production Railway deployment, database migration or production environment-variable change is performed by this branch preparation alone.

## Safety and operational constraints

- Scans are limited indicators, not a guarantee of safety.
- Optional URL sharing with PhishTank requires explicit user consent.
- Do not request wallet recovery phrases, private keys, wallet passwords or transaction approvals.
- Monitor provider rate limits, request volume, server load, database growth and backup delivery.
