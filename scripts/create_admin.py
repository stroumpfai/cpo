#!/usr/bin/env python3
"""
Bootstrap the CPO application by creating the admin account in the SQLite
database (running the schema migrations first if needed).

Usage:
    python scripts/create_admin.py [--db /path/to/cpo.db]

The script prompts for a password interactively. Run it once on a fresh
install. Not needed when upgrading an existing JSON-based install: the app
imports config.json (including the admin account) on first startup.
"""
import argparse
import getpass
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Dependencies (bcrypt, SQLAlchemy, alembic) live in the backend venv, not in
# the system Python. If they're missing, find the project venv and re-execute.
# ---------------------------------------------------------------------------
try:
    import bcrypt  # noqa: F401
    import sqlalchemy  # noqa: F401
    import alembic  # noqa: F401
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
        "Error: backend dependencies are not available in this Python.\n"
        "Install them first, then retry:\n\n"
        "  python -m venv venv\n"
        "  venv/bin/pip install -r backend/requirements.txt\n"
        "  venv/bin/python scripts/create_admin.py\n"
    )

_BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(_BACKEND_DIR))

BCRYPT_ROUNDS = 12


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode()


def main():
    parser = argparse.ArgumentParser(description="Create the initial CPO admin account")
    parser.add_argument(
        "--db",
        default=None,
        help="Path to the SQLite database (default: $DATABASE_PATH or /app/data/cpo.db)",
    )
    args = parser.parse_args()

    if args.db:
        os.environ["DATABASE_PATH"] = args.db
    # backend/config.py requires JWT_SECRET at import; the database bootstrap
    # itself doesn't use it, so provide a placeholder if the env lacks one.
    os.environ.setdefault("JWT_SECRET", "bootstrap-placeholder")

    from sqlalchemy import func, select

    import config
    import db
    import schema

    db.run_migrations()

    with db.get_engine().begin() as conn:
        if conn.execute(select(func.count()).select_from(schema.admins)).scalar():
            print(f"Admin already exists in {config.DATABASE_PATH}.")
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

    with db.get_engine().begin() as conn:
        conn.execute(
            schema.admins.insert().values(
                username=username,
                password_hash=hash_password(pw1),
                created_at=datetime.now(tz=timezone.utc).isoformat(),
            )
        )

    print(f"\n✓ Admin account created in {config.DATABASE_PATH}")
    print("  Start the app and log in as", username, "to create CPO accounts.")


if __name__ == "__main__":
    main()
