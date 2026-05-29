import os

# File paths (overridable via environment for local dev)
CONFIG_PATH = os.getenv("CONFIG_PATH", "/app/config/config.json")
DATA_DIR = os.getenv("DATA_DIR", "/app/data")

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
