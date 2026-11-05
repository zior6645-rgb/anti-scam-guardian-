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
- Refund command is restricted to `ADMIN_TELEGRAM_IDS`, but the production environment currently has no configured admin ID.
- `/paysupport` asks the buyer to provide receipt details to the bot but does not expose an operator support contact.
- Real payments are currently disabled.

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
- Tests cover admin/support gating, one-time pass wording, private-only `/myid`, support-contact fallback, and idempotency.
- CI applies the same bot patch before tests and the Docker image applies the same patch before runtime.
- README and Persian launch docs state that Telegram Stars are the only permitted in-app checkout for this digital service.
- Production payment variables remain unchanged and disabled.
