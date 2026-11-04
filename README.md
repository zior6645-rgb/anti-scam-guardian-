# AntiScam Guardian

Telegram-first crypto safety assistant MVP. Product focus: user-consented suspicious URL screening and basic TON wallet / Jetton metadata checks.

## Current release

This repository deploys release **0.2.4** from the root archive `AntiScamGuardian-0.2.4-Railway.zip`. The archive must be uploaded to the repository root on branch `railway-deploy-024` before merging or deploying.

See [RAILWAY-DEPLOY-fa.md](./RAILWAY-DEPLOY-fa.md) for the Persian deployment walkthrough.

## Safety and product limitations

- Payments are disabled by default. Do not accept real payments until legal, policy, and end-to-end payment checks are complete.
- In Telegram, digital goods and subscription access inside bots and Mini Apps must use Telegram Stars (XTR); direct TON checkout to unlock digital in-app services is not the intended path.
- TON Connect is read-only for wallet identification. The app must never request seed phrases/private keys or custody user funds.
- URL and wallet checks are indicators, not a guarantee that an asset, address, token, or transaction is safe. Never use a scan result as the sole reason to approve a transaction.
- External URL reputation lookup is only performed after the user opts in.
- SQLite deployment requires one Railway replica and a persistent volume mounted at `/data`.

## Required GitHub artifact

Upload the exact file `AntiScamGuardian-0.2.4-Railway.zip` to the repository root on branch `railway-deploy-024`. GitHub Actions will run Python tests, build the Vite Mini App, and build the Docker image. Merge only after the workflow succeeds.
