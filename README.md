# AntiScam Guardian

Telegram-first crypto safety assistant MVP.

The full project source is stored in `payload/` as Base64 chunks of a compressed XZ archive. Follow [REBUILD.md](./REBUILD.md) to reconstruct and extract it.

## Included
- Telegram bot and Mini App starter
- Telegram WebApp `initData` verification
- TON Connect wallet connection (no seed phrases/private keys)
- TON address checksum validation
- URL and basic risk heuristics
- SQLite persistence and usage limits
- Optional Telegram Stars subscription code (disabled by default)
- Docker and GitHub Actions workflow

## Important
This is an MVP starter, not an audited wallet product or a production-grade security oracle. Risk checks are heuristic and may miss scams or flag legitimate services. Do not rely on results to authorize transactions. The app must never request seed phrases/private keys or custody user funds.

Payments are disabled by default. Before charging users, review applicable laws, Telegram's current payment rules, privacy requirements, and relevant provider terms. Never accept real funds until those reviews and end-to-end tests are complete.

## Test status
The backend test suite passed in the build environment (14 tests). The frontend dependency installation/build did not complete in that environment, so the production frontend build is **not verified**. The project is not deployed or live.
