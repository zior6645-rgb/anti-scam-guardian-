# Customer-readiness verification

Last verified: 2026-11-07  
Branch: `release/customer-readiness`  
Verified commit: `ca598467f706075e48f3b1c6613fc1562e2d3a14`  
GitHub Actions: [Run 200 — release verification](https://github.com/zior6645-rgb/anti-scam-guardian-/actions/runs/42408755495)

This branch contains customer-readiness work only. It has not been deployed to Railway and does not alter the production service, production database, or production secrets.

## Changes included

- Added an isolated SQLite execution test for successful-payment delivery, duplicate updates, refund replay, delivery after billing is disabled, and invalid product/currency/amount handling.
- Added an assembled API/database test for plan quotas, blocking before provider work, provider failures, invalid input, duplicate Pro activation, and refund-driven access changes.
- Added shared quota formatting for account and post-scan states. The UI reports configured Free/Pro limits and remaining scans instead of implying unlimited Pro usage.
- Added a report download generated locally in the browser as plain text. It includes observed indicators, provider evidence where available, limitations, privacy cautions, and verification steps.
- Added a history action to reopen the saved report.
- Corrected duplicate-payment acknowledgement so a replay does not falsely claim the user still has active Pro access after refund or expiry.
- Removed the duplicate Git path `scripts/reconstruct.py\n`; the canonical `scripts/reconstruct.py` remains.
- Kept the release workflow's `release/customer-readiness` push trigger. The release verification workflow builds and tests only; it contains no Railway deploy step.

## Verified by GitHub Actions

Run [42408755495](https://github.com/zior6645-rgb/anti-scam-guardian-/actions/runs/42408755495), for commit `ca598467f706075e48f3b1c6613fc1562e2d3a14`, completed successfully.

| Check | Actual result |
|---|---:|
| Source reconstruction using `scripts/reconstruct.py` | Passed |
| Python compile check | Passed |
| Python `unittest` suite | **117 passed, 0 failed** |
| JavaScript `node:test` suite | **14 passed, 0 failed, 0 skipped** |
| Fresh frontend dependency install (Node 22) | Passed; 29 packages added |
| Deepmerge security regression test | Passed |
| Vite production frontend build | Passed |
| Production Docker image build | Passed |

The Vite build emitted the existing large-chunk advisory; it did not fail the build. The Docker image was built by the CI runner and was not deployed.

The release workflow was subsequently tightened to run the result-metadata patcher twice in sequence, checking that the patcher is safe to reapply. The Docker build uses the same repeated check. The dependency/Bandit workflow is also enabled for this branch. Those additional workflow changes require their own successful run before being considered verified.

## Not verified / release blockers

- No Telegram Stars Test Server purchase, successful-payment delivery through Telegram, or refund was performed. The Python payment tests use temporary SQLite and isolated handler execution only.
- No production payment mode or price was enabled. Keep production billing disabled until the separate legal and Telegram test gates are approved.
- No Railway service, live volume, live database, environment variable, secret, or deployment was changed by this work.
- No real Telegram WebView/browser interaction or end-to-end device test was performed. The JavaScript checks are automated unit/source tests and the Vite build.
- A real backup file was not restored using the owner's production encryption secret in a separate environment.
- No independent penetration test or external security audit has been completed.
- Operator identity, target-market eligibility, terms, privacy/retention/deletion policy, support responsiveness, and eligibility to receive Telegram Stars rewards need owner/legal verification.
- Scam-detection precision and false-positive/false-negative rates have not been established on a representative labelled dataset. URL checks remain heuristic; TonAPI metadata is not a smart-contract audit or safety guarantee.
- No paying-customer or willingness-to-pay validation has been performed.

## Release decision

**Status: technically verified beta changes; not approved for paid public launch.**

The passing CI demonstrates repeatable source reconstruction, automated code-level checks, a production frontend build, and Docker image creation. It does not prove live Telegram payment/refund behavior, production deployment, legal eligibility, independent security, scam-detection accuracy, or customer demand.

Before live billing, complete the Telegram Stars test lifecycle, refund/entitlement reconciliation review, live support verification, legal/privacy review, backup restore drill, independent security review, and a limited user pilot. Do not market the scanner as a security oracle or guarantee that a wallet, URL, or token is safe.
