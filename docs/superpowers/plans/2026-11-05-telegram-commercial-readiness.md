# Telegram Commercial Readiness Implementation Plan

> **For agentic workers:** Execute inline in the isolated `commercial-readiness-026` branch. Use test-driven development for the patch script. This work must not enable real payments or add crypto checkout.

**Goal:** Make the existing Stars-only 30-day Pro pass safer to configure and support, while documenting the payment restrictions that apply to this Telegram Mini App.

**Architecture:** Preserve the archived release and its overlay-based build. Add a deterministic Python patch script for `app/bot.py`, apply it in both CI and Docker, and verify the patched output through regression tests. Keep current production settings and deployment untouched until the new branch passes CI and review.

**Tech Stack:** Python 3.12, aiogram 3.31, unittest, Docker, GitHub Actions, Railway.

**Spec:** `docs/specs/telegram-commercial-readiness.md`

## Global Constraints
- Digital Pro services sold inside Telegram use Telegram Stars (`XTR`) only.
- `PAYMENTS_MODE=disabled` and `STARS_MONTHLY_PRICE=0` stay unchanged.
- Never request seed phrases, private keys, wallet passwords, or transaction approvals.
- Keep the one-instance Telegram poller, SQLite volume at `/data`, and existing `python -m app.runtime` command.
- Never store operator secrets or support contact credentials in source files.

## Review Focus
- Missing admin IDs: the app must not issue or approve a new invoice.
- Missing support contact: the app must not issue or approve a new invoice.
- A group-chat `/myid` request: it must not reveal a user's numeric ID publicly.
- Missing support contact on `/paysupport`: the bot must clearly state that live billing is not ready.
- Existing valid payment: this patch must not add a new blocker to the already-existing successful-payment fulfilment path.

---

### Task 1: Safe operator and support behavior

**Files:**
- Create: `overlays/app/apply_bot_operator_patch.py`
- Create: `overlays/tests/test_bot_operator_patch.py`
- Modify during build: `app/bot.py` inside the reconstructed archive

**Interfaces:**
- Produces: `patch_bot_source(source: str) -> str`, an idempotent transformation of the archived `app/bot.py`.
- Consumes: Existing `settings.admin_telegram_ids`, `settings.payments_mode`, `settings.stars_monthly_price`, and the `SUPPORT_CONTACT` environment variable.

- [ ] Write tests for invoice gating, one-off pass text, private-only `/myid`, support contact/fallback, and idempotency.
- [ ] Run the test module and verify the expected failures occur against an identity patch.
- [ ] Implement `patch_bot_source(source: str) -> str` with exact-anchor, once-only replacements and AST validation.
- [ ] Run the test module again; all cases must pass.
- [ ] Apply the patch to a fixture twice and verify the output is stable.

### Task 2: Integrate the patch into build and CI

**Files:**
- Modify: `Dockerfile`
- Modify: `.github/workflows/railway-ci.yml`
- Modify: `overlays/tests/test_bot_operator_patch.py`
- Modify: `overlays/app/apply_bot_operator_patch.py`

**Interfaces:**
- Docker and CI both apply `apply_bot_operator_patch.py` to the reconstructed `app/bot.py`.
- CI copies the operator-patch test and patch utility into the reconstructed source tree before unittest discovery.

- [ ] Add the patch utility to the Docker build context and execute it before copying the app into the final runtime image.
- [ ] Add the patch utility/test copy steps to archive reconstruction in CI.
- [ ] Apply the operator patch before compilation and the full Python test suite in CI.
- [ ] Run the full workflow and inspect the backend test count, frontend build, and Docker image build.

### Task 3: Commercial and wallet policy documentation

**Files:**
- Modify: `README.md`
- Modify: `PRELAUNCH-CHECKLIST-fa.md`
- Modify: `RAILWAY-DEPLOY-fa.md`
- Create: `docs/specs/telegram-commercial-readiness.md`
- Create: `docs/superpowers/plans/2026-11-05-telegram-commercial-readiness.md`

- [ ] Document XTR-only digital checkout in Telegram and explicitly rule out TON/USDT deposits for unlocking the in-Telegram Pro service.
- [ ] State that Pro is a one-off 30-day pass and does not auto-renew.
- [ ] Document `ADMIN_TELEGRAM_IDS` and `SUPPORT_CONTACT` as required before live Stars invoices can be issued.
- [ ] Preserve disabled production payment settings and the pre-launch legal/test blockers.

### Task 4: Review and readiness verification

- [ ] Read the complete diff and check that it does not change production variables or deploy settings.
- [ ] Verify all GitHub Actions steps are green.
- [ ] Keep the pull request in draft until the remaining owner/legal/test blockers are resolved.
- [ ] Do not claim the product is commercially ready while any mandatory blocker remains.
