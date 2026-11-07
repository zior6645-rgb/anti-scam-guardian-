# Reconstruct once using the same patch sequence as CI and local verification.
FROM python:3.12-slim AS source
WORKDIR /bundle
COPY payload/ ./payload/
COPY overlays/ ./overlays/
COPY scripts/reconstruct.py ./scripts/reconstruct.py
RUN python scripts/reconstruct.py /source

FROM node:22-alpine AS frontend
WORKDIR /web
COPY --from=source /source/anti-scam-guardian/web/package.json ./package.json
RUN npm install --no-audit --no-fund
COPY --from=source /source/anti-scam-guardian/web/ ./
RUN node ./patch-deepmerge-security.mjs && node ./test-deepmerge-security.mjs && node ./apply-result-metadata.mjs && node ./apply-result-metadata.mjs && npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gosu && rm -rf /var/lib/apt/lists/*
COPY --from=source /source/anti-scam-guardian/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && pip install --no-cache-dir "cryptography>=50,<51"
COPY --from=source /source/anti-scam-guardian/app ./app
COPY --from=frontend /app/static ./app/static
COPY --from=source /source/anti-scam-guardian/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN useradd --create-home --uid 10001 appuser && mkdir -p /data && chown -R appuser:appuser /app /data && chmod 755 /usr/local/bin/docker-entrypoint.sh
EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["python", "-m", "app.backup_supervisor"]
