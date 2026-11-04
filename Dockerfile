# Build the application from the versioned source archive, then overlay reviewed release fixes.
FROM alpine:3.20 AS source
RUN apk add --no-cache xz
WORKDIR /bundle
COPY payload/release-0.2.4.tar.xz.b64.part* /bundle/payload/
COPY overlays/app/scanner.py /bundle/overlay/scanner.py
RUN cat /bundle/payload/release-0.2.4.tar.xz.b64.part* | base64 -d > /bundle/release.tar.xz \
    && mkdir -p /source \
    && tar -xJf /bundle/release.tar.xz -C /source \
    && cp /bundle/overlay/scanner.py /source/anti-scam-guardian/app/scanner.py

FROM node:22-alpine AS frontend
WORKDIR /web
COPY --from=source /source/anti-scam-guardian/web/package.json ./package.json
RUN npm install --no-audit --no-fund
COPY --from=source /source/anti-scam-guardian/web/ ./
RUN npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends gosu \
    && rm -rf /var/lib/apt/lists/*
COPY --from=source /source/anti-scam-guardian/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir "uvicorn>=0.30,<1"
COPY --from=source /source/anti-scam-guardian/app ./app
COPY --from=frontend /app/static ./app/static
COPY --from=source /source/anti-scam-guardian/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
COPY overlays/service_supervisor.py /app/service_supervisor.py
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /data \
    && chown -R appuser:appuser /app /data \
    && chmod 755 /usr/local/bin/docker-entrypoint.sh /app/service_supervisor.py
EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["python", "/app/service_supervisor.py"]
