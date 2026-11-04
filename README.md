# AntiScam Guardian

Telegram-first crypto safety assistant MVP. The complete starter project is packaged in **[anti-scam-guardian-mvp.zip](./anti-scam-guardian-mvp.zip)**.

## Scope
- Telegram bot and Mini App starter
- Telegram WebApp `initData` verification
- TON Connect frontend integration (wallet connection only; no seed phrases/private keys)
- TON address checksum validation
- URL and basic on-chain risk heuristics
- SQLite persistence and usage limits
- Optional Telegram Stars subscription path (disabled by default)
- Docker and GitHub Actions test workflow

## Important
This is an MVP starter, not a production security oracle or audited wallet product. Risk checks are heuristic and may miss scams or flag legitimate services. Do not rely on the result to approve transactions. The app must never request seed phrases/private keys or custody user funds.

Payments are disabled by default. Before charging users, review applicable laws, Telegram's current payment rules, privacy requirements, and the relevant provider terms. Never accept real funds until this is reviewed and tested.

## Quick start
1. Download and extract `anti-scam-guardian-mvp.zip`.
2. Copy `.env.example` to `.env` and configure the bot token and deployment URLs.
3. Follow the Persian setup guide in `راهنمای-راه‌اندازی.md`.
4. Run tests using the commands in the project README.

## Test status
Backend test suite passed in the build environment. Frontend dependency installation/build was not completed in that environment, so the frontend production build is **not verified**.

## Language
Project setup guide: [راهنمای-راه‌اندازی.md](./anti-scam-guardian-mvp.zip)
