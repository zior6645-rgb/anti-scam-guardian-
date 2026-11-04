# AntiScam Guardian

Telegram-first TON security assistant. This repository currently contains a release-readiness candidate, not a commercially approved security product.

## Current state

- The original source release is reconstructed from six Base64 chunks under payload/release-0.2.4.tar.xz.b64.part*.
- Reviewed code overlays live under overlays/; the Docker build and CI apply the same overlays before packaging and testing.
- The scanner supports heuristic URL indicators, TON account metadata, and TON Jetton master metadata through TonAPI.
- The container supervisor starts both the FastAPI Mini App/API and the Telegram long-polling bot in one service.
- The service is configured for one replica because Telegram long polling must not run in multiple replicas with the same bot token.
- Payments remain disabled.

## Verification

GitHub Actions reconstructs the source archive, applies the overlays, compiles and tests the backend, builds the Vite Mini App, builds the Docker image, and verifies that the production image uses the combined process supervisor.

## Important product limitations

- URL scanning is local heuristic analysis only. It is not connected to a live phishing/reputation feed in this release.
- TON account and Jetton responses are provider metadata, not a complete security verdict or smart-contract audit.
- TonAPI whitelist does not mean guaranteed safe; graylist and blacklist are provider classifications and can change.
- A false is_scam value means only that TonAPI did not currently flag the account; it does not prove safety.
- Never ask for or accept seed phrases, private keys, wallet passwords, or transfers to scan an address.
- Do not claim that a result guarantees an asset, address, token, contract, or transaction is safe.
- The service requires valid Telegram Mini App initData in production; development authentication must remain disabled.
- SQLite must use a persistent volume mounted at /data, and the service must run as one replica.

## Deployment

See RAILWAY-DEPLOY-fa.md. Deployment still requires an operator-controlled hosting account, a fresh BotFather token, a public HTTPS domain, and a persistent volume. The local Termux setup is for testing only and is not a public production host.

## Monetization status

Telegram in-bot digital subscriptions must use Telegram Stars (XTR). This repository does not yet include a complete Stars purchase, pre-checkout, successful-payment, subscription lifecycle, refund, or reconciliation implementation. Keep PAYMENTS_MODE=disabled; do not accept real payments until these flows and the legal/policy review are complete.

## Before public launch

1. Revoke any BotFather token previously exposed outside the secret manager and issue a new token.
2. Deploy with HTTPS, a persistent /data volume, one replica, ALLOW_DEV_AUTH=false, and a short Telegram init-data freshness window.
3. Complete URL threat-intelligence integration with a licensed provider and verify consent/privacy requirements.
4. Complete Jetton/account regression tests against live and mocked provider responses.
5. Complete a security review, abuse/rate-limit review, privacy notice, terms, and operator contact details.
6. Implement and end-to-end test Telegram Stars payments, renewals, cancellations, refunds, and support procedures before enabling monetization.

This project is not independently audited and is not a security oracle. It must not be marketed as providing guaranteed scam detection or transaction safety.
