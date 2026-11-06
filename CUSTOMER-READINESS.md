# Customer-readiness verification

## Changes in this iteration
- Corrected duplicate-payment acknowledgement: it no longer asserts active Pro access after expiry/refund.
- Added execution tests for the actual successful-payment handler with temporary SQLite: first delivery, duplicate delivery, replay after refund, delivery after payments disabled, and invalid product/currency/amount.
- Added local plain-text report downloads with evidence, limitations, privacy notice and suggested verification steps.
- Added full report viewing from scan history.

## Verified locally
- Fresh release reconstructed using scripts/reconstruct.py.
- Python unittest suite: 117 tests passed.
- JavaScript node:test suite: 14 tests passed.
- Deepmerge prototype-poisoning regression passed.
- Frontend patcher applied twice successfully (idempotence).
- Vite production build passed, with 541.59 kB JS chunk warning.

Build used Node 24 and the previously installed/patched frontend dependencies copied from the earlier verification. The deepmerge patcher rejects reapplication when no unpatched files remain; the independent security regression passed. This iteration is not a fresh npm-install reproducibility check. Docker/CI target Node 22/Python 3.12; local Python is 3.11. Docker build and browser/Telegram UI interaction were not verified here.

## Not completed / release blockers
- No GitHub or Railway CLI, or associated access environment variables, were found. No commit, push, deployment, or live-service modification was performed.
- No live Telegram purchase, delivery or refund was performed. Payments remain disabled in the documented deployment configuration.
- Live operator/support setup, backups/restore, provider availability and Telegram authentication need operator verification.
- No paying-customer validation exists. Added functionality does not prove willingness to pay.

Do not market this as defect-free or deploy with real payments enabled on the basis of these tests alone. The existing public bot URL is not evidence that these changes are deployed.

## Handoff
The accompanying ZIP contains selected local repository changes, including preceding reconstruction/quota work, plus this report. It is NOT a standalone application or online preview. Apply the files to the intended repository at the reviewed base (782ffcd), review the diff, reconstruct and run checks following REBUILD.md, then build/deploy the root Dockerfile in the authorized project. Keep payments disabled until practical billing checks are approved and completed.
