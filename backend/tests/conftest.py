"""
Shared pytest fixtures for admin and CPO endpoint tests.

Provides:
  - isolated storage (fresh SQLite DB per test)
  - a pre-seeded config (admin + one CPO)
  - a TestClient for the main FastAPI app
  - bearer-header helpers
"""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

import config as cfg_module
import db
import schema
import storage
from main import app
from routers.auth import clear_login_attempts
from models import AdminRecord, ConfigFile, CPORecord, Pizza, TeamRecord
from security import create_token
from utils import generate_link, hash_password, new_id

ADMIN_PASSWORD = "adminpass"                  # NOSONAR
SECOND_ADMIN_PASSWORD = "otherpass77"         # NOSONAR
CPO_PASSWORD = "cpopass99"                    # NOSONAR
SECOND_TEAM_MEMBER_PASSWORD = "teammate123"   # NOSONAR


@pytest.fixture(autouse=True)
def reset_login_attempts():
    clear_login_attempts()
    yield
    clear_login_attempts()


@pytest.fixture()
def tmp_storage(tmp_path, monkeypatch):
    """Point the app at a fresh SQLite database (and legacy paths) under tmp_path."""
    monkeypatch.setattr(cfg_module, "DATABASE_PATH", str(tmp_path / "cpo.db"))
    monkeypatch.setattr(cfg_module, "CONFIG_PATH", str(tmp_path / "config" / "config.json"))
    monkeypatch.setattr(cfg_module, "DATA_DIR", str(tmp_path / "data"))
    db.dispose_engine()
    schema.metadata.create_all(db.get_engine())
    yield tmp_path
    db.dispose_engine()


@pytest.fixture()
def seeded_config(tmp_storage):
    # Team and CPO login share one id here — same simplification the Alembic
    # migration and json_migration.py use for pre-existing single-CPO teams.
    # It keeps every existing test's use of seeded_config["cpo_id"] as a
    # team-scoping argument to storage functions working unchanged.
    shared_id = new_id()
    admin = AdminRecord(
        id=1,
        username="admin",
        password_hash=hash_password(ADMIN_PASSWORD),
        created_at=datetime.now(tz=timezone.utc),
    )
    team = TeamRecord(
        id=shared_id,
        team_name="Engineering",
        unique_link=generate_link(),
        created_at=datetime.now(tz=timezone.utc),
    )
    cpo = CPORecord(
        id=shared_id,
        team_id=shared_id,
        username="john",
        email="john@example.com",
        password_hash=hash_password(CPO_PASSWORD),
        created_at=datetime.now(tz=timezone.utc),
    )
    cfg = ConfigFile(admins=[admin], cpos=[cpo], teams=[team])
    storage.save_config(cfg)
    return {"admin": admin, "cpo": cpo, "cpo_id": shared_id, "team": team, "team_id": shared_id}


@pytest.fixture()
def seeded_menu(seeded_config):
    """Default menu with two pizzas for the seeded CPO (needed to open sessions)."""
    menu = storage.create_menu(seeded_config["team_id"], "Default")
    menu.pizzas = [
        Pizza(id=new_id(), name="Margherita", price=12.50),
        Pizza(id=new_id(), name="Pepperoni", price=13.50),
    ]
    storage.save_menu(menu)
    return menu


@pytest.fixture()
def second_admin(seeded_config):
    return storage.insert_admin(
        username="admin2",
        password_hash=hash_password(SECOND_ADMIN_PASSWORD),
        created_at=datetime.now(tz=timezone.utc).isoformat(),
    )


@pytest.fixture()
def second_team_member(seeded_config):
    """A second CPO login sharing the SAME team as seeded_config — for testing
    peer/shared-team scenarios (both logins see the same menus/sessions)."""
    cfg = storage.load_config()
    cpo = CPORecord(
        id=new_id(),
        team_id=seeded_config["team_id"],
        username="jane",
        email="jane@example.com",
        password_hash=hash_password(SECOND_TEAM_MEMBER_PASSWORD),
        created_at=datetime.now(tz=timezone.utc),
    )
    cfg.cpos.append(cpo)
    storage.save_config(cfg)
    return cpo


@pytest.fixture()
def client(tmp_storage):
    return TestClient(app)


@pytest.fixture()
def admin_headers(seeded_config):
    token = create_token("1", "admin", version=0)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def second_admin_headers(second_admin):
    token = create_token(str(second_admin.id), "admin", version=0)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def cpo_headers(seeded_config):
    token = create_token(seeded_config["cpo_id"], "cpo")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def second_team_member_headers(second_team_member):
    token = create_token(second_team_member.id, "cpo")
    return {"Authorization": f"Bearer {token}"}
