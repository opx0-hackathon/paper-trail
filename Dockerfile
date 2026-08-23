# --- stage 1: build the React bundle --------------------------------------
FROM node:22-alpine AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

# --- stage 2: python runtime ----------------------------------------------
FROM python:3.11-slim AS runtime

# uv gives us the same lockfile-based sync CI uses
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PAPERTRAIL_HOST=0.0.0.0 \
    PAPERTRAIL_PORT=8790 \
    PAPERTRAIL_WEB_DIST=/app/web/dist \
    PAPERTRAIL_DB=/data/papertrail.db \
    PAPERTRAIL_MIGRATIONS=/app/migrations \
    PAPERTRAIL_PROMPTS=/app/prompts \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Deps first — cache-friendly
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Then the source. README.md is copied because pyproject.toml references
# it and hatchling validates it exists during the project install.
COPY README.md ./
COPY src/ ./src/
COPY migrations/ ./migrations/
COPY prompts/ ./prompts/
COPY --from=web /web/dist ./web/dist
RUN uv sync --frozen --no-dev

# SQLite lives on a volume so `docker compose up -d` never wipes sessions
RUN install -d /data && chown -R nobody:nogroup /data /app
USER nobody

EXPOSE 8790
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8790/healthz',timeout=3).status==200 else 1)"

CMD ["papertrail-serve"]
