import os

# File paths (overridable via environment for local dev)
# CONFIG_PATH and DATA_DIR now only locate legacy JSON data for the one-time
# import into SQLite; all live data is in the database at DATABASE_PATH.
CONFIG_PATH = os.getenv("CONFIG_PATH", "/app/config/config.json")
DATA_DIR = os.getenv("DATA_DIR", "/app/data")
DATABASE_PATH = os.getenv("DATABASE_PATH", os.path.join(DATA_DIR, "cpo.db"))

# JWT
_jwt_secret = os.getenv("JWT_SECRET")
if not _jwt_secret:
    raise RuntimeError(
        "JWT_SECRET environment variable is not set. "
        "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
    )
JWT_SECRET: str = _jwt_secret
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_DAYS = 14

# Session rules
GRACE_PERIOD_MINUTES = 2
RATE_LIMIT_SECONDS = 5

# Security
BCRYPT_ROUNDS = 12
MIN_LINK_LENGTH = 16

# Maximum accepted request body size (menu imports are the largest legitimate payload)
MAX_BODY_BYTES = 1_000_000

# Auth cookie: Secure flag should stay on in production (TLS-terminating proxy);
# set COOKIE_SECURE=false only for plain-HTTP local runs.
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() == "true"
