import os

# File paths (overridable via environment for local dev)
CONFIG_PATH = os.getenv("CONFIG_PATH", "/app/config/config.json")
DATA_DIR = os.getenv("DATA_DIR", "/app/data")

# JWT
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_DAYS = 30

# Session rules
GRACE_PERIOD_MINUTES = 2
RATE_LIMIT_SECONDS = 5

# Security
BCRYPT_ROUNDS = 12
MIN_LINK_LENGTH = 16
