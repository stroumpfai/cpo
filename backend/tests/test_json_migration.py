"""
Tests for the one-time legacy JSON → SQLite import (json_migration.py)
and for Alembic/metadata schema parity.
"""
import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, func, inspect, select

import config as cfg_module
import db
import schema
import storage
from json_migration import migrate_legacy_json_if_needed
from utils import generate_link, hash_password, new_id

# Fixtures from conftest.py: tmp_storage (fresh DB + patched legacy paths)


CPO_ID = "11111111-1111-4111-8111-111111111111"
SESSION_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
SESSION_B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


@pytest.fixture()
def legacy_tree(tmp_storage):
    """A realistic legacy JSON layout under the patched CONFIG_PATH/DATA_DIR."""
    config_path = tmp_storage / "config" / "config.json"
    data_dir = tmp_storage / "data"
    now = datetime.now(tz=timezone.utc).isoformat()

    _write(config_path, {
        "admin": {"username": "admin", "password_hash": hash_password("pw"), "created_at": now},
        "cpos": [{
            "id": CPO_ID,
            "username": "john",
            "email": "john@example.com",
            "password_hash": hash_password("pw"),
            "team_name": "Engineering",
            "unique_link": generate_link(),
            "created_at": now,
        }],
    })
    _write(data_dir / CPO_ID / "menu.json", {
        "cpo_id": CPO_ID,
        "pizzas": [
            {"id": new_id(), "name": "Margherita", "price": 12.5},
            {"id": new_id(), "name": "Diavola", "price": 14.0},
        ],
        "pizzeria_url": "https://pizzeria.example",
    })
    _write(data_dir / CPO_ID / f"{SESSION_A}.json", {
        "id": SESSION_A,
        "cpo_id": CPO_ID,
        "team_name": "Engineering",
        "session_date": "2026-05-15",
        "start_time": "11:30",
        "end_time": "12:00",
        "grace_period_minutes": 2,
        "created_at": "2026-05-15T09:00:00Z",
        "closed_at": None,
        # legacy order rows: no comment / received / quantity keys
        "orders": [{
            "id": new_id(),
            "session_id": SESSION_A,
            "member_name": "Alice",
            "pizza_id": "p1",
            "pizza_name": "Margherita",
            "pizza_price": 12.5,
            "total_price": 12.5,
            "created_at": "2026-05-15T11:47:39Z",
            "client_ip": "10.0.0.1",
        }],
    })
    _write(data_dir / CPO_ID / f"{SESSION_B}.json", {
        "id": SESSION_B,
        "cpo_id": CPO_ID,
        "team_name": "Engineering",
        "session_date": "2026-05-16",
        "start_time": "11:30",
        "end_time": "12:00",
        "grace_period_minutes": 2,
        "created_at": "2026-05-16T09:00:00Z",
        "closed_at": "2026-05-16T12:05:00Z",
        "orders": [],
    })
    return {"config_path": config_path, "data_dir": data_dir}


def test_import_populates_database(legacy_tree):
    migrate_legacy_json_if_needed()

    cfg = storage.load_config()
    assert [a.username for a in cfg.admins] == ["admin"]
    assert cfg.admins[0].id == 1
    assert cfg.admins[0].token_version == 0
    assert [c.id for c in cfg.cpos] == [CPO_ID]

    menu = storage.get_default_menu(CPO_ID)
    assert menu is not None
    assert menu.is_default is True
    assert [p.name for p in menu.pizzas] == ["Margherita", "Diavola"]
    assert menu.pizzeria_url == "https://pizzeria.example"

    sessions = storage.list_sessions(CPO_ID)
    assert [s.id for s in sessions] == [SESSION_A, SESSION_B]
    assert sessions[1].closed_at is not None
    # legacy sessions are linked to the menu created during the import
    assert [s.menu_id for s in sessions] == [menu.id, menu.id]

    # legacy orders get model defaults for missing fields
    order = sessions[0].orders[0]
    assert order.member_name == "Alice"
    assert order.comment is None
    assert order.received is False
    assert order.quantity == 1


def test_import_archives_json_tree(legacy_tree):
    migrate_legacy_json_if_needed()

    assert not (legacy_tree["data_dir"] / CPO_ID).exists()
    archived = legacy_tree["data_dir"] / "_migrated_json" / CPO_ID
    assert (archived / "menu.json").exists()
    assert (archived / f"{SESSION_A}.json").exists()
    assert not legacy_tree["config_path"].exists()
    assert legacy_tree["config_path"].with_suffix(".json.migrated").exists()


def test_import_is_idempotent(legacy_tree):
    migrate_legacy_json_if_needed()
    migrate_legacy_json_if_needed()  # admin row present → no-op

    cfg = storage.load_config()
    assert len(cfg.cpos) == 1
    assert len(storage.list_sessions(CPO_ID)) == 2


def test_import_skips_fresh_install(tmp_storage):
    migrate_legacy_json_if_needed()  # no config.json → no-op
    with pytest.raises(FileNotFoundError):
        storage.load_config()


def test_corrupt_session_file_rolls_back_everything(legacy_tree):
    bad = legacy_tree["data_dir"] / CPO_ID / f"{SESSION_B}.json"
    bad.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(Exception):
        migrate_legacy_json_if_needed()

    # transaction rolled back: DB empty, JSON tree untouched
    with db.get_engine().connect() as conn:
        assert conn.execute(select(func.count()).select_from(schema.admins)).scalar() == 0
        assert conn.execute(select(func.count()).select_from(schema.cpos)).scalar() == 0
    assert legacy_tree["config_path"].exists()
    assert (legacy_tree["data_dir"] / CPO_ID / "menu.json").exists()


# ---------------------------------------------------------------------------
# Alembic ↔ schema.metadata parity
# ---------------------------------------------------------------------------

def test_migration_0003_backfills_session_menu(tmp_path, monkeypatch):
    """Upgrading a pre-multi-menu database links existing sessions to the
    CPO's default menu."""
    import os
    from alembic import command
    from alembic.config import Config

    db_path = tmp_path / "upgrade.db"
    monkeypatch.setattr(cfg_module, "DATABASE_PATH", str(db_path))

    backend_dir = os.path.dirname(os.path.abspath(db.__file__))
    alembic_cfg = Config(os.path.join(backend_dir, "alembic.ini"))
    alembic_cfg.set_main_option("script_location", os.path.join(backend_dir, "migrations"))
    alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")

    command.upgrade(alembic_cfg, "0002")

    engine = create_engine(f"sqlite:///{db_path}")
    menu_id = new_id()
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "INSERT INTO cpos (id, username, email, password_hash, team_name, unique_link, created_at) "
            "VALUES (?, 'john', 'john@example.com', 'x', 'Engineering', ?, '2026-01-01T00:00:00Z')",
            (CPO_ID, generate_link()),
        )
        conn.exec_driver_sql(
            "INSERT INTO menus (id, cpo_id, is_default) VALUES (?, ?, 1)",
            (menu_id, CPO_ID),
        )
        conn.exec_driver_sql(
            "INSERT INTO sessions (id, cpo_id, team_name, session_date, start_time, end_time, created_at) "
            "VALUES (?, ?, 'Engineering', '2026-05-15', '11:30', '12:00', '2026-05-15T09:00:00Z')",
            (SESSION_A, CPO_ID),
        )
    engine.dispose()

    command.upgrade(alembic_cfg, "head")

    engine = create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        row = conn.exec_driver_sql("SELECT menu_id FROM sessions WHERE id = ?", (SESSION_A,)).first()
    engine.dispose()
    assert row[0] == menu_id


def test_migration_0004_defaults_existing_cpos_to_name(tmp_path, monkeypatch):
    """Upgrading an existing database leaves every CPO in the current
    name-based behaviour rather than silently switching them to email."""
    import os
    from alembic import command
    from alembic.config import Config

    db_path = tmp_path / "upgrade.db"
    monkeypatch.setattr(cfg_module, "DATABASE_PATH", str(db_path))

    backend_dir = os.path.dirname(os.path.abspath(db.__file__))
    alembic_cfg = Config(os.path.join(backend_dir, "alembic.ini"))
    alembic_cfg.set_main_option("script_location", os.path.join(backend_dir, "migrations"))
    alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")

    command.upgrade(alembic_cfg, "0003")

    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "INSERT INTO cpos (id, username, email, password_hash, team_name, unique_link, created_at) "
            "VALUES (?, 'john', 'john@example.com', 'x', 'Engineering', ?, '2026-01-01T00:00:00Z')",
            (CPO_ID, generate_link()),
        )
    engine.dispose()

    # Pinned to 0004 (not head): migration 0006 later moves member_identifier
    # from cpos to teams entirely — see test_migration_0006_splits_teams_from_cpos
    # for coverage of that move. This test is about 0004's default in isolation.
    command.upgrade(alembic_cfg, "0004")

    engine = create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        row = conn.exec_driver_sql(
            "SELECT member_identifier FROM cpos WHERE id = ?", (CPO_ID,)
        ).first()
    engine.dispose()
    assert row[0] == "name"


def test_migration_0006_splits_teams_from_cpos(tmp_path, monkeypatch):
    """Upgrading a pre-teams database splits each CPO row into a teams row
    (reusing the CPO's own id as the team's id) plus a slimmed-down cpos row
    with a team_id FK — and backfills menus/sessions.team_id the same way."""
    import os
    from alembic import command
    from alembic.config import Config

    db_path = tmp_path / "upgrade.db"
    monkeypatch.setattr(cfg_module, "DATABASE_PATH", str(db_path))

    backend_dir = os.path.dirname(os.path.abspath(db.__file__))
    alembic_cfg = Config(os.path.join(backend_dir, "alembic.ini"))
    alembic_cfg.set_main_option("script_location", os.path.join(backend_dir, "migrations"))
    alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")

    command.upgrade(alembic_cfg, "0005")

    engine = create_engine(f"sqlite:///{db_path}")
    unique_link = generate_link()
    menu_id = new_id()
    with engine.begin() as conn:
        # Full v5 cpos row: id/username/email/password_hash/team_name/
        # unique_link/created_at/token_version/currency/member_identifier/
        # stats_reset_at — the complete pre-0006 column set.
        conn.exec_driver_sql(
            "INSERT INTO cpos (id, username, email, password_hash, team_name, "
            "unique_link, created_at, token_version, currency, member_identifier, "
            "stats_reset_at) "
            "VALUES (?, 'john', 'john@example.com', 'x', 'Engineering', ?, "
            "'2026-01-01T00:00:00Z', 0, 'EUR', 'email', '2026-02-01T00:00:00Z')",
            (CPO_ID, unique_link),
        )
        conn.exec_driver_sql(
            "INSERT INTO menus (id, cpo_id, is_default) VALUES (?, ?, 1)",
            (menu_id, CPO_ID),
        )
        conn.exec_driver_sql(
            "INSERT INTO sessions (id, cpo_id, team_name, session_date, start_time, end_time, created_at) "
            "VALUES (?, ?, 'Engineering', '2026-05-15', '11:30', '12:00', '2026-05-15T09:00:00Z')",
            (SESSION_A, CPO_ID),
        )
    engine.dispose()

    command.upgrade(alembic_cfg, "head")

    engine = create_engine(f"sqlite:///{db_path}")
    insp = inspect(engine)
    with engine.connect() as conn:
        team_row = conn.exec_driver_sql(
            "SELECT id, team_name, unique_link, currency, member_identifier "
            "FROM teams WHERE id = ?",
            (CPO_ID,),
        ).first()
        cpo_row = conn.exec_driver_sql(
            "SELECT team_id FROM cpos WHERE id = ?", (CPO_ID,)
        ).first()
        menu_row = conn.exec_driver_sql(
            "SELECT team_id FROM menus WHERE id = ?", (menu_id,)
        ).first()
        session_row = conn.exec_driver_sql(
            "SELECT team_id FROM sessions WHERE id = ?", (SESSION_A,)
        ).first()
    cpo_columns = {c["name"] for c in insp.get_columns("cpos")}
    engine.dispose()

    # A teams row exists with the same id as the old cpo id, carrying the
    # fields that used to live on the cpos row.
    assert team_row is not None
    assert team_row[0] == CPO_ID
    assert team_row[1] == "Engineering"
    assert team_row[2] == unique_link
    assert team_row[3] == "EUR"
    assert team_row[4] == "email"

    # The cpos row now points at that team via team_id, and no longer has
    # the old team-level columns.
    assert cpo_row[0] == CPO_ID
    assert "team_name" not in cpo_columns
    assert "unique_link" not in cpo_columns
    assert "currency" not in cpo_columns
    assert "member_identifier" not in cpo_columns
    assert "stats_reset_at" not in cpo_columns
    assert "team_id" in cpo_columns

    # Menus and sessions were backfilled with the same team_id.
    assert menu_row[0] == CPO_ID
    assert session_row[0] == CPO_ID


def test_alembic_head_matches_metadata(tmp_path, monkeypatch):
    """The Alembic migration chain must produce the schema tests create via
    metadata.create_all() — guards against the two drifting apart."""
    monkeypatch.setattr(cfg_module, "DATABASE_PATH", str(tmp_path / "alembic.db"))
    db.run_migrations()

    engine = create_engine(f"sqlite:///{tmp_path / 'alembic.db'}")
    insp = inspect(engine)

    migrated_tables = set(insp.get_table_names()) - {"alembic_version"}
    assert migrated_tables == set(schema.metadata.tables)

    for name, table in schema.metadata.tables.items():
        migrated_cols = {c["name"] for c in insp.get_columns(name)}
        assert migrated_cols == {c.name for c in table.columns}, name
        migrated_indexes = {
            i["name"] for i in insp.get_indexes(name)
            if not i["name"].startswith("sqlite_autoindex")
        }
        metadata_indexes = {i.name for i in table.indexes}
        assert migrated_indexes == metadata_indexes, name
    engine.dispose()
