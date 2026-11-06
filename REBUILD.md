# Rebuild and verify the current release

The deployable release is reconstructed from `payload/release-0.2.4.tar.xz.b64.part*` **plus the current overlays**. Extracting an archive alone omits the refund, operator, product-limit, runtime and frontend changes.

Use the same reconstruction entry point as the root Dockerfile and CI:

```bash
python scripts/reconstruct.py release
```

Run this from the repository root with Python 3.12 (the Docker/CI version). `release` must not exist; choose a new output directory for each clean verification. This works in PowerShell too when `python` points to the supported interpreter.

The script only writes local files and runs local patchers. It does not start the bot, connect to a deployment, or change a live database. Output is `release/anti-scam-guardian/`.

## Backend checks

Create and activate an isolated Python environment, then:

```bash
cd release/anti-scam-guardian
python -m pip install -r requirements.txt
python -m pip install "cryptography>=50,<51"
python -m compileall -q app tests
python -m unittest discover -s tests -v
```

## Frontend checks and production assets

With Node 22 and npm available, from the reconstructed project:

```bash
cd web
node --test ../tests/*.mjs
npm install --no-audit --no-fund
node patch-deepmerge-security.mjs
node test-deepmerge-security.mjs
node apply-result-metadata.mjs
npm run build
```

The production frontend is written to `../app/static/`. Reconstruction alone does not produce these assets or apply the Node-based frontend patchers.

## Deployment image

From the **original repository root**, not the extracted project:

```bash
docker build -t anti-scam-guardian:release-readiness .
```

The root Dockerfile performs reconstruction, frontend patching/building, and runtime assembly. Do not substitute the legacy Dockerfile inside the payload for the root Dockerfile.

Local tests and a successful build are not proof of deployment, Telegram WebApp authentication, live payments, Pro delivery, refunds, or backup restoration. Follow `PRELAUNCH-CHECKLIST-fa.md` and `RAILWAY-DEPLOY-fa.md`; keep payments disabled until operational verification is complete.

## Historical archives

`payload/archive.tar.xz.b64.part*` is a historical archive and is **not** the current deployment input. Do not use the old manual archive-extraction instructions to reproduce the current release.
