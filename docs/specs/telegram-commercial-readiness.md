# Telegram Commercial Readiness — Specification

## Goal
Prepare AntiScam Guardian to sell its existing 30-day Pro access through the payment method Telegram permits for digital services, while preventing checkout from starting until refund administration and customer support are configured.

## Binding platform constraints
- Pro access, scan quotas, and scan-history extensions are digital services delivered inside a Telegram bot/Mini App.
- The in-Telegram checkout currency is Telegram Stars (XTR) only.
- TON Connect remains a wallet connection protocol for permitted blockchain interactions; it is not a crypto checkout for the Mini App's digital Pro service.
- Do not create deposit addresses, credit user balances, or unlock Pro after direct TON/USDT transfers inside the Telegram product.
- Keep `PAYMENTS_MODE=disabled` and `STARS_MONTHLY_PRICE=0` until the operator/legal and Telegram Stars test gates pass.

## Current observed behavior
- `/premium` uses a Stars invoice path behind environment gates.
- The invoice describes 30 days, but the user-facing title does not clearly distinguish a one-off pass from recurring billing.
- Pre-checkout validates amount, currency, payload, and terms acceptance.
- Successful-payment updates grant the 30-day entitlement through the existing idempotent database operation.
- `ADMIN_TELEGRAM_IDS` and `SUPPORT_CONTACT` are now configured in Railway, and `/paysupport` was manually checked.
- The live refund command is restricted to the configured operator, but it still needs a durable pending/refund-reconciliation state if Telegram accepts a refund and the local database write then fails.
- The live payment mode remains disabled.

## Verified deployment status (2026-11-05)
- The production Railway service is currently attached to `commercial-readiness-026` and runs commit `40cbe06a`; it is online with a single bot polling process.
- HTTPS, the `/data` persistent volume, `ADMIN_TELEGRAM_IDS`, and `SUPPORT_CONTACT` are configured. `/paysupport` returned the configured contact during a manual check.
- Do not describe PR #3 as "not deployed"; the branch is deployed even though the PR is still open and unmerged.
- Production billing remains disabled (`PAYMENTS_MODE=disabled`, `STARS_MONTHLY_PRICE=0`).
- PR #4 (`payment-hardening-026`) is isolated from the production source branch and adds pending-refund reservation and admin reconciliation. It is a draft and is not deployed.

## Changes in scope
1. Add a private-chat-only `/myid` command so the owner can retrieve their own numeric Telegram ID without involving a third-party bot.
2. Describe Pro as a one-time 30-day pass that does not auto-renew.
3. Refuse to issue or approve a Stars invoice unless:
   - `PAYMENTS_MODE=telegram_stars`
   - `STARS_MONTHLY_PRICE > 0`
   - at least one `ADMIN_TELEGRAM_IDS` value is configured
   - a non-empty `SUPPORT_CONTACT` is configured
   - the user has accepted the current terms.
4. Make `/paysupport` display the configured support contact; when missing, clearly state that payments must remain disabled.
7. Reserve a refund locally before the Telegram API call; distinguish pending, confirmed, and released states; require explicit admin confirmation for manual reconciliation; do not retry an uncertain refund blindly.
5. Add tests for the archive-patching script and include it in Docker and CI.
6. Document the Stars-only policy, the manual-renewal behavior, and the operator setup blockers.

## Out of scope
- Direct TON/USDT checkout or deposits for unlocking digital features in the Telegram Mini App.
- Custody of user funds, seed phrases, private keys, or user wallet recovery material.
- Enabling live payments, selecting a price, inventing operator identity/contact details, or completing legal review.
- Automatic recurring charges; the current product is a one-off 30-day pass.

## Acceptance criteria
- The patch script is deterministic and idempotent.
- The patched bot source compiles.
- Tests cover admin/support gating, one-time pass wording, private-only `/myid`, support-contact fallback, idempotency, pending refund reservation, duplicate refund prevention, and manual reconciliation guards.
- CI applies the same bot patch before tests and the Docker image applies the same patch before runtime.
- README and Persian launch docs state that Telegram Stars are the only permitted in-app checkout for this digital service.
- Production payment variables remain unchanged and disabled.
