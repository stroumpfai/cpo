# ── Stage 1: build Python wheels ────────────────────────────────────────────
# Use the full image so Rust/gcc are available for compiling pydantic-core.
FROM python:3.13 AS builder

WORKDIR /build
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Stage 2: slim runtime image ──────────────────────────────────────────────
FROM python:3.13-slim

# Version baked in at build time.
# APP_MAJOR and APP_BUILD are set here; GIT_COMMIT is passed via --build-arg:
#   docker build --build-arg GIT_COMMIT=$(git rev-parse --short HEAD) ...
ARG APP_MAJOR=1
ARG APP_BUILD=0
ARG GIT_COMMIT=unknown

ENV CPO_VERSION="${APP_MAJOR}.${APP_BUILD}" \
    CPO_COMMIT="${GIT_COMMIT}"

WORKDIR /app

# Copy installed packages and console-scripts from the build stage.
COPY --from=builder /usr/local/lib/python3.13/site-packages \
                    /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn

# Copy backend source (includes pre-built frontend in dist/ after `npm run build`)
COPY backend/ ./

# Ensure storage volume mount-points exist inside the image.
RUN mkdir -p /app/config /app/data

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
