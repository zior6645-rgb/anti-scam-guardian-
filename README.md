# AntiScam Guardian

Telegram-first crypto safety assistant MVP. Product focus: user-consented suspicious URL screening and basic TON wallet / Jetton metadata checks.

## Current release

The default branch contains release **0.2.4**. The source archive is stored as six Base64 chunks under `payload/release-0.2.4.tar.xz.b64.part*`. The root Dockerfile reconstructs the source archive and builds the Mini App and Python runtime.

See [RAILWAY-DEPLOY-fa.md](./RAILWAY-DEPLOY-fa.md) for the Persian deployment walkthrough. No manual ZIP upload or VPS is required.

## Verification

GitHub Actions verifies archive reconstruction, Python compilation and tests, the Vite production build, and the Docker image build.

## Safety and product limitations

- Payments are disabled by default. Do not accept real payments until legal, policy, and end-to-end payment checks are complete.
- In Telegram, digital goods and subscription access inside bots and Mini Apps must use Telegram Stars (XTR); direct TON checkout to unlock digital in-app services is not the intended path.
- TON Connect is read-only for wallet identification. The app must never request seed phrases/private keys or custody user funds.
- URL and wallet checks are indicators, not a guarantee that an asset, address, token, or transaction is safe. Never use a scan result as the sole reason to approve a transaction.
- External URL reputation lookup is only performed after the user opts in.
- SQLite deployment requires one Railway replica and a persistent volume mounted at `/data`.

## Deployment

1. Sign in to Railway with GitHub.
2. Deploy the `zior6645-rgb/anti-scam-guardian-` repository from GitHub.
3. Add a persistent Volume mounted at `/data`, enable Railway public networking, and keep the replica count at one.
4. Set the environment variables described in [RAILWAY-DEPLOY-fa.md](./RAILWAY-DEPLOY-fa.md).
5. Keep `PAYMENTS_MODE=disabled` until payment, legal and security checks are complete.

This is a release candidate, not an independently audited security oracle. Risk checks can miss scams or flag legitimate services.
