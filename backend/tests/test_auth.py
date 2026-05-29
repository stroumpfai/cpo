"""
Tests for POST /api/auth/login and /api/auth/logout,
plus security.py helpers (token creation / decoding / dependencies).
"""
import json
import pytest
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

import storage
import config as cfg_module
import security
from main import app
from models import AdminRecord, ConfigFile, CPORecord
from security import create_token, get_current_user, require_admin, require_cpo
from utils import generate_link, hash_password, new_id


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

ADMIN_PASSWORD = "adminpass"  # NOSONAR
CPO_PASSWORD = "cpopass99"    # NOSONAR


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    config_file = tmp_path / "config" / "config.json"
    monkeypatch.setattr(storage, "CONFIG_PATH", str(config_file))
    monkeypatch.setattr(cfg_module, "CONFIG_PATH", str(config_file))

    admin = AdminRecord(
        username="admin",
        password_hash=hash_password(ADMIN_PASSWORD),
        created_at=datetime.now(tz=timezone.utc),
    )
    cpo = CPORecord(
        id=new_id(),
        username="john",
        email="john@example.com",
        password_hash=hash_password(CPO_PASSWORD),
        team_name="Engineering",
        unique_link=generate_link(),
        created_at=datetime.now(tz=timezone.utc),
    )
    cfg = ConfigFile(admin=admin, cpos=[cpo])
    storage.save_config(cfg)
    return {"admin": admin, "cpo": cpo}


@pytest.fixture()
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# Login — admin
# ---------------------------------------------------------------------------

def test_admin_login_success(client, isolated_config):
    r = client.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PASSWORD})
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "admin"
    assert "token" in body
    assert body["expires_in"] == 1209600


def test_admin_login_wrong_password(client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})  # NOSONAR
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Login — CPO
# ---------------------------------------------------------------------------

def test_cpo_login_success(client):
    r = client.post("/api/auth/login", json={"username": "john", "password": CPO_PASSWORD})
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "cpo"
    assert "token" in body


def test_cpo_login_wrong_password(client):
    r = client.post("/api/auth/login", json={"username": "john", "password": "wrong"})  # NOSONAR
    assert r.status_code == 401


def test_unknown_user_login(client):
    r = client.post("/api/auth/login", json={"username": "nobody", "password": "x"})  # NOSONAR
    assert r.status_code == 401


def test_login_rate_limit(client):
    """Fifth wrong attempt succeeds (401); sixth is blocked (429)."""
    for _ in range(5):
        client.post("/api/auth/login", json={"username": "john", "password": "wrong"})  # NOSONAR
    r = client.post("/api/auth/login", json={"username": "john", "password": "wrong"})  # NOSONAR
    assert r.status_code == 429


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

def test_logout(client):
    r = client.post("/api/auth/logout")
    assert r.status_code == 200
    assert r.json()["message"] == "Logged out"


# ---------------------------------------------------------------------------
# Token round-trip
# ---------------------------------------------------------------------------

def test_create_and_decode_admin_token():
    token = create_token("admin", "admin")
    import jwt
    payload = jwt.decode(token, cfg_module.JWT_SECRET, algorithms=[cfg_module.JWT_ALGORITHM])
    assert payload["sub"] == "admin"
    assert payload["role"] == "admin"


def test_create_and_decode_cpo_token(isolated_config):
    cpo_id = isolated_config["cpo"].id
    token = create_token(cpo_id, "cpo", version=0)
    import jwt
    payload = jwt.decode(token, cfg_module.JWT_SECRET, algorithms=[cfg_module.JWT_ALGORITHM])
    assert payload["sub"] == cpo_id
    assert payload["role"] == "cpo"
    assert payload["ver"] == 0


# ---------------------------------------------------------------------------
# Protected dependency behaviour
# ---------------------------------------------------------------------------

from fastapi import FastAPI
from fastapi.testclient import TestClient as TC
from typing import Annotated
from security import CurrentUser

_test_app = FastAPI()


@_test_app.get("/admin-only")
def admin_only(user: Annotated[CurrentUser, __import__("fastapi").Depends(require_admin)]):
    return {"user_id": user.user_id}


@_test_app.get("/cpo-only")
def cpo_only(user: Annotated[CurrentUser, __import__("fastapi").Depends(require_cpo)]):
    return {"user_id": user.user_id}


@pytest.fixture()
def guarded():
    return TC(_test_app)


def test_admin_token_accesses_admin_route(guarded):
    token = create_token("admin", "admin")
    r = guarded.get("/admin-only", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["user_id"] == "admin"


def test_cpo_token_denied_on_admin_route(guarded):
    token = create_token("cpo-123", "cpo")
    r = guarded.get("/admin-only", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


def test_admin_token_denied_on_cpo_route(guarded):
    token = create_token("admin", "admin")
    r = guarded.get("/cpo-only", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


def test_cpo_token_accesses_cpo_route(guarded, isolated_config):
    cpo_id = isolated_config["cpo"].id
    token = create_token(cpo_id, "cpo", version=0)
    r = guarded.get("/cpo-only", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


def test_no_token_rejected(guarded):
    r = guarded.get("/admin-only")
    assert r.status_code == 401  # HTTPBearer returns 401 when header missing (FastAPI >= 0.116)


def test_invalid_token_rejected(guarded):
    r = guarded.get("/admin-only", headers={"Authorization": "Bearer not.a.token"})
    assert r.status_code == 401
