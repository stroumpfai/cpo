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

    menu = storage.load_menu(CPO_ID)
    assert [p.name for p in menu.pizzas] == ["Margherita", "Diavola"]
    assert menu.pizzeria_url == "https://pizzeria.example"

    sessions = storage.list_sessions(CPO_ID)
    assert [s.id for s in sessions] == [SESSION_A, SESSION_B]
    assert sessions[1].closed_at is not None

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
