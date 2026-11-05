# Reconstruct the pinned source archive, overlay reviewed scanning code, and build the Mini App metadata renderer.
# The archived app.runtime module starts the API and exactly one Telegram bot poller.
FROM alpine:3.20 AS source
RUN apk add --no-cache xz
WORKDIR /bundle
COPY payload/release-0.2.4.tar.xz.b64.part* /bundle/payload/
COPY overlays/app/scanner.py /bundle/overlay/scanner.py
COPY overlays/web /bundle/overlay/web/
RUN cat /bundle/payload/release-0.2.4.tar.xz.b64.part* | base64 -d > /bundle/release.tar.xz && mkdir -p /source && tar -xJf /bundle/release.tar.xz -C /source && cp /bundle/overlay/scanner.py /source/anti-scam-guardian/app/scanner.py && cp /bundle/overlay/web/result-metadata.js /source/anti-scam-guardian/web/src/result-metadata.js && cp /bundle/overlay/web/wallet-policy-note.js /source/anti-scam-guardian/web/src/wallet-policy-note.js

FROM node:22-alpine AS frontend
WORKDIR /web
COPY --from=source /source/anti-scam-guardian/web/package.json ./package.json
RUN npm install --no-audit --no-fund
COPY --from=source /source/anti-scam-guardian/web/ ./
COPY --from=source /bundle/overlay/web/apply-result-metadata.mjs ./apply-result-metadata.mjs
COPY --from=source /bundle/overlay/web/patch-deepmerge-security.mjs ./patch-deepmerge-security.mjs
COPY --from=source /bundle/overlay/web/test-deepmerge-security.mjs ./test-deepmerge-security.mjs
RUN node ./patch-deepmerge-security.mjs && node ./test-deepmerge-security.mjs && node ./apply-result-metadata.mjs && npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gosu && rm -rf /var/lib/apt/lists/*
COPY --from=source /source/anti-scam-guardian/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && pip install --no-cache-dir "cryptography>=42,<48"
COPY --from=source /source/anti-scam-guardian/app ./app
COPY overlays/app/backup_supervisor.py ./app/backup_supervisor.py
COPY overlays/app/restore_backup.py ./app/restore_backup.py
COPY overlays/app/apply-database-refund-patch.py /tmp/apply-database-refund-patch.py
COPY overlays/app/apply_bot_operator_patch.py /tmp/apply_bot_operator_patch.py
RUN python /tmp/apply-database-refund-patch.py /app/app/database.py && python /tmp/apply_bot_operator_patch.py /app/app/bot.py && rm /tmp/apply-database-refund-patch.py /tmp/apply_bot_operator_patch.py
COPY --from=frontend /app/static ./app/static
COPY --from=source /source/anti-scam-guardian/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN useradd --create-home --uid 10001 appuser && mkdir -p /data && chown -R appuser:appuser /app /data && chmod 755 /usr/local/bin/docker-entrypoint.sh
EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["python", "-m", "app.backup_supervisor"]
