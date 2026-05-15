#!/usr/bin/env python3
"""
Bootstrap the CPO application by creating the initial config.json with an
admin account.

Usage:
    python scripts/create_admin.py [--config /path/to/config.json]

The script will prompt for a password interactively.  Run it once before
starting the container for the first time.
"""
import argparse
import getpass
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# bcrypt is installed in the backend venv, not in the system Python.
# If it's missing, find the project venv and re-execute with it.
# ---------------------------------------------------------------------------
try:
    import bcrypt  # noqa: E402
except ModuleNotFoundError:
    _root = Path(__file__).resolve().parent.parent
    _candidates = [
        _root / "venv"         / "bin" / "python3",
        _root / ".venv"        / "bin" / "python3",
        _root / "backend" / "venv"  / "bin" / "python3",
        _root / "backend" / ".venv" / "bin" / "python3",
    ]
    _venv_py = next((p for p in _candidates if p.exists()), None)
    if _venv_py:
        raise SystemExit(subprocess.call([str(_venv_py), __file__] + sys.argv[1:]))
    sys.exit(
        "Error: bcrypt is not available in this Python.\n"
        "Install the backend dependencies first, then retry:\n\n"
        "  python -m venv venv\n"
        "  venv/bin/pip install -r backend/requirements.txt\n"
        "  venv/bin/python scripts/create_admin.py\n"
    )


DEFAULT_CONFIG_PATH = os.getenv("CONFIG_PATH", "/app/config/config.json")
BCRYPT_ROUNDS = 12


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode()


def main():
    parser = argparse.ArgumentParser(description="Create initial CPO admin config")
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG_PATH,
        help=f"Path to config.json (default: {DEFAULT_CONFIG_PATH})",
    )
    args = parser.parse_args()

    config_path = Path(args.config)

    if config_path.exists():
        print(f"Config already exists at {config_path}. Delete it first to re-initialise.")
        sys.exit(1)

    print("Creating admin account for CPO application.")
    username = input("Admin username [admin]: ").strip() or "admin"
    while True:
        pw1 = getpass.getpass("Admin password (min 8 chars): ")
        if len(pw1) < 8:
            print("Password must be at least 8 characters.")
            continue
        pw2 = getpass.getpass("Confirm password: ")
        if pw1 != pw2:
            print("Passwords do not match.")
            continue
        break

    config = {
        "admin": {
            "username": username,
            "password_hash": hash_password(pw1),
            "created_at": datetime.now(tz=timezone.utc).isoformat(),
        },
        "cpos": [],
    }

    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    print(f"\n✓ Config written to {config_path}")
    print("  Start the app and log in as", username, "to create CPO accounts.")


if __name__ == "__main__":
    main()
