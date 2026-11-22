# AntiScam Guardian

A free Telegram-first security screening assistant for suspicious URLs, TON wallet addresses and TON Jetton contracts.

## Product model

- Every user gets the same Free experience.
- URL, TON wallet and Jetton scans have no application-imposed daily quota.
- Scan history has no Free/Pro split or application-imposed item cap.
- There are no Pro plans, paid features, invoices, subscriptions, checkout flows or in-bot payment handlers.
- The Mini App displays a single “Free plan · unlimited scans” status.
- Wallet and token scans use manually entered public addresses. The Mini App does not include wallet connection or transaction approval.

“Unlimited” means this application does not block a user after a fixed number of scans or history items. It does not mean external providers, Telegram, Railway, network capacity or hosting costs are unlimited. Provider rate limits, temporary outages, abuse protection and infrastructure capacity may affect service availability.

## Scanning capabilities

- URL syntax checks and local heuristic indicators.
- Optional PhishTank lookup only after explicit per-scan user consent and only when an operator-supplied application key is configured.
- TON account metadata through TonAPI, including the provider’s current scam indicator when available.
- TON Jetton master metadata through TonAPI, including name, symbol, decimals, supply, mintability, holder count and provider verification classification.
- Telegram Mini App authentication, searchable scan history, risk-level filters, per-item and bulk deletion, user-triggered JSON history export, and local report export.
- Persistent SQLite storage and automatic encrypted database backups.

## Important limitations

- URL checks do not fetch or execute the submitted website. Local heuristics are not a live threat-intelligence verdict.
- PhishTank is one source, not a complete phishing or malware feed. External lookup is only performed after consent; URL query strings may contain secrets.
- TonAPI results are public provider metadata, not a wallet reputation audit, token economics review, liquidity analysis, honeypot test, bytecode audit or transaction simulation.
- A whitelist or a false scam indicator is not proof of safety. Provider classifications can change and scams may be missed.
- Never request seed phrases, private keys, wallet passwords, transfers or transaction approval to perform a scan.

## Deployment

See the Persian [Railway deployment guide](./RAILWAY-DEPLOY-fa.md).

The Docker image reconstructs the pinned source archive and applies the free/unlimited and wallet-free product patches before building the Mini App and runtime. The release workflow verifies source reconstruction, backend tests, JavaScript tests, frontend build and Docker build.

Required runtime configuration includes BOT_TOKEN, BOT_USERNAME, ENVIRONMENT=production, ALLOW_DEV_AUTH=false, DATABASE_PATH=/data/guardian.sqlite3 and TELEGRAM_INITDATA_MAX_AGE_SECONDS=600. The bot also needs ADMIN_TELEGRAM_IDS and BACKUP_ENCRYPTION_KEY for encrypted backups.

No payment-related environment variables are read by the free build. FREE_SCANS_PER_DAY, PAYMENTS_MODE and STARS_MONTHLY_PRICE are not used.

This is a screening tool, not an independently audited security service or a guarantee that a link, wallet, token or transaction is safe.
