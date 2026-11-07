# Customer-readiness verification

Last verified: 2026-11-07  
Branch: `release/customer-readiness`  
Code and workflow commit verified: `10d5b71793c8b6e9522df4e7c1a914a1850fb906`

Release verification: [GitHub Actions run 42409276051](https://github.com/zior6645-rgb/anti-scam-guardian-/actions/runs/42409276051) — **success**.  
Dependency/security audit: [GitHub Actions run 42409276044](https://github.com/zior6645-rgb/anti-scam-guardian-/actions/runs/42409276044) — **success**.

This branch contains customer-readiness work only. It has not been deployed to Railway and does not alter the production service, production database, or production secrets.

## Changes included

- Added an isolated SQLite execution test for successful-payment delivery, duplicate updates, refund replay, delivery after billing is disabled, and invalid product/currency/amount handling.
- Added an assembled API/database test for plan quotas, blocking before provider work, provider failures, invalid input, duplicate Pro activation, and refund-driven access changes.
- Added shared quota formatting for account and post-scan states. The UI reports configured Free/Pro limits and remaining scans instead of implying unlimited Pro usage.
- Added a report download generated locally in the browser as plain text. It includes observed indicators, provider evidence where available, limitations, privacy cautions, and suggested verification steps.
- Added a history action to reopen a saved full report.
- Corrected duplicate-payment acknowledgement so a replay does not falsely claim the user still has active Pro access after refund or expiry.
- Removed the duplicate Git path `scripts/reconstruct.py\n`; the canonical `scripts/reconstruct.py` remains.
- Kept the `release/customer-readiness` push trigger. The release verification workflow builds and tests only; it has no Railway deploy step.
- Added this branch to the dependency/security audit workflow.
- Added a second execution of the result-metadata frontend patcher in both CI and Docker builds to verify repeat application.
- Release reconstruction runs every production Python patcher twice and fails if the second pass changes any patched source file.

## Release verification results

Run [42409276051](https://github.com/zior6645-rgb/anti-scam-guardian-/actions/runs/42409276051), on commit `10d5b71793c8b6e9522df4e7c1a914a1850fb906`, completed successfully.

| Check | Actual result |
|---|---:|
| Source reconstruction using `scripts/reconstruct.py` | Passed |
| Python compile check | Passed |
| Python `unittest` suite | **117 passed, 0 failed** |
| JavaScript `node:test` suite | **14 passed, 0 failed, 0 skipped** |
| Clean frontend dependency install (Node 22) | Passed; 29 packages added |
| Deepmerge prototype-poisoning regression | Passed |
| Result-metadata patcher run twice in CI | Passed |
| Vite production frontend build | Passed |
| Result-metadata patcher run twice in Docker build | Passed |
| Production Docker image build | Passed |

The Vite build emitted the existing large-chunk advisory; it did not fail the build. The Docker image was built by the GitHub Actions runner and was not deployed.

## Dependency and static-security audit

Run [42409276044](https://github.com/zior6645-rgb/anti-scam-guardian-/actions/runs/42409276044) completed successfully. All four jobs passed:

- Python dependency audit: `pip-audit` reported **No known vulnerabilities found**.
- Mini App dependency audit: `npm audit --audit-level=high` passed. The audit still reports **two low-severity upstream findings** through `@tonconnect/ui` / `deepmerge` (GHSA-gcqx-w48m-w2h4); npm reported no upstream fix available. The local build-time mitigation and its prototype-poisoning regression test passed. The upstream advisory remains open and must not be described as fixed.
- Python static analysis: Bandit reported no remaining findings (Low=0, Medium=0, High=0) after the narrow, documented `nosec` exceptions.
- Archived product-flow inspection: passed.

## Not verified / release blockers

- No Telegram Stars Test Server purchase, successful-payment delivery through Telegram, or refund was performed. Payment tests use temporary SQLite and isolated handler execution only.
- No production payment mode or price was enabled. Keep production billing disabled until separate legal and Telegram test gates are approved.
- No Railway service, live volume, live database, environment variable, secret, or deployment was changed by this work.
- No real Telegram WebView/browser interaction or end-to-end device test was performed. JavaScript checks are automated tests and the Vite build.
- A real backup file was not restored using the owner's production encryption secret in a separate environment.
- No independent penetration test or external security audit has been completed.
- Operator identity, target-market eligibility, terms, privacy/retention/deletion policy, support responsiveness, and eligibility to receive Telegram Stars rewards need owner/legal verification.
- Scam-detection precision and false-positive/false-negative rates have not been established on a representative labelled dataset. URL checks remain heuristic; TonAPI metadata is not a smart-contract audit or safety guarantee.
- No paying-customer or willingness-to-pay validation has been performed.

## Release decision

**Status: technically verified beta changes; not approved for paid public launch.**

Passing CI demonstrates repeatable source reconstruction, code-level tests, frontend production build, Docker image creation, and the configured dependency/static-analysis checks. It does not prove live Telegram payment/refund behavior, production deployment, legal eligibility, independent security, scam-detection accuracy, or customer demand.

Before live billing, complete the Telegram Stars test lifecycle, refund/entitlement reconciliation review, live support verification, legal/privacy review, backup restore drill, independent security review, and a limited user pilot. Do not market the scanner as a security oracle or guarantee that a wallet, URL, or token is safe.
