"""
SQLite engine lifecycle.

The engine is created lazily on first use, reading config.DATABASE_PATH at
call time so tests can monkeypatch the path and call dispose_engine() to
re-point at a fresh database.

Every pooled connection gets the pragmas set below: foreign keys enforced,
WAL journaling (readers don't block the writer — the SSE poll loop reads
while orders are inserted), and a busy timeout instead of immediate
"database is locked" errors.
"""
from __future__ import annotations

import os
import threading
from pathlib import Path

from sqlalchemy import Engine, create_engine, event

_engine: Engine | None = None
_engine_lock = threading.Lock()


def _set_pragmas(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                import config

                Path(config.DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
                engine = create_engine(
                    f"sqlite:///{config.DATABASE_PATH}",
                    # Connections are pooled and never used by two threads at
                    # once (TestClient worker thread, asyncio.to_thread reads).
                    connect_args={"check_same_thread": False},
                )
                event.listens_for(engine, "connect")(_set_pragmas)
                _engine = engine
    return _engine


def dispose_engine() -> None:
    """Close all pooled connections and forget the engine (tests, re-pointing)."""
    global _engine
    with _engine_lock:
        if _engine is not None:
            _engine.dispose()
            _engine = None


def run_migrations() -> None:
    """Bring the database schema to the latest Alembic revision."""
    from alembic import command
    from alembic.config import Config

    import config

    backend_dir = os.path.dirname(os.path.abspath(__file__))
    alembic_cfg = Config(os.path.join(backend_dir, "alembic.ini"))
    alembic_cfg.set_main_option("script_location", os.path.join(backend_dir, "migrations"))
    alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{config.DATABASE_PATH}")
    command.upgrade(alembic_cfg, "head")
