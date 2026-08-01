# ── Stage 1: build Python wheels ────────────────────────────────────────────
# Use the full image so Rust/gcc are available for compiling pydantic-core.
FROM python:3.14 AS builder

WORKDIR /build
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Stage 2: slim runtime image ──────────────────────────────────────────────
FROM python:3.14-slim

# Version baked in at build time, shown in the UI (CPO sidebar, admin header):
#   docker build --build-arg APP_VERSION=1.5.0 \
#                --build-arg GIT_COMMIT=$(git rev-parse --short HEAD) ...
# APP_VERSION is used verbatim — deliberately one value rather than the major
# and build parts it used to be assembled from, because concatenating them
# silently mangled any full version string put in either half.
# Both can also be overridden at runtime (e.g. CPO_VERSION in .env), which
# takes precedence over what is baked in here and needs no rebuild.
ARG APP_VERSION=dev
ARG GIT_COMMIT=unknown

ENV CPO_VERSION="${APP_VERSION}" \
    CPO_COMMIT="${GIT_COMMIT}"

WORKDIR /app

# Copy installed packages and console-scripts from the build stage.
COPY --from=builder /usr/local/lib/python3.14/site-packages \
                    /usr/local/lib/python3.14/site-packages
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn

# Copy backend source (includes pre-built frontend in dist/ after `npm run build`)
COPY backend/ ./

# Ensure storage volume mount-points exist inside the image.
RUN mkdir -p /app/config /app/data \
    && adduser --disabled-password --gecos "" appuser \
    && chown -R appuser /app/config /app/data

USER appuser

EXPOSE 8002

# Single process only: login/order rate limiting and SSE tokens (security.py,
# routers/auth.py, services/order_service.py) are per-process in-memory state
# with no shared backing store. Adding --workers (or running multiple
# replicas without a shared store, e.g. Redis) would split that state across
# processes and silently defeat the rate limits.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]
