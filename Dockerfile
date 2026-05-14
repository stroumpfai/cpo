# ── Stage 1: build Python wheels ────────────────────────────────────────────
# Use the full image so Rust/gcc are available for compiling pydantic-core.
FROM python:3.13 AS builder

WORKDIR /build
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Stage 2: slim runtime image ──────────────────────────────────────────────
FROM python:3.13-slim

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
