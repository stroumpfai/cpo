import pytest
from fastapi.testclient import TestClient

from main import app


# All fixtures come from conftest.py (client, seeded_config, admin_headers, cpo_headers)


# ---------------------------------------------------------------------------
# GET /api/admin/cpos
# ---------------------------------------------------------------------------

def test_list_cpos_returns_seeded_cpo(client, seeded_config, admin_headers):
    r = client.get("/api/admin/cpos", headers=admin_headers)
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["username"] == "john"
    assert "password_hash" not in data[0]


def test_list_cpos_requires_admin(client, seeded_config, cpo_headers):
    r = client.get("/api/admin/cpos", headers=cpo_headers)
    assert r.status_code == 403


def test_list_cpos_requires_auth(client, seeded_config):
    r = client.get("/api/admin/cpos")
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# POST /api/admin/cpos
# ---------------------------------------------------------------------------

def test_create_cpo_success(client, seeded_config, admin_headers):
    r = client.post(
        "/api/admin/cpos",
        json={
            "username": "alice",
            "email": "alice@example.com",
            "team_name": "Marketing",
            "initial_password": "securepass",
        },
        headers=admin_headers,
    )
    assert r.status_code == 201
    body = r.json()
    assert body["username"] == "alice"
    assert body["team_name"] == "Marketing"
    assert "id" in body
    assert "unique_link" in body
    assert len(body["unique_link"]) >= 16


def test_create_cpo_duplicate_username(client, seeded_config, admin_headers):
    r = client.post(
        "/api/admin/cpos",
        json={
            "username": "john",   # already exists
            "email": "other@example.com",
            "team_name": "Sales",
            "initial_password": "securepass",
        },
        headers=admin_headers,
    )
    assert r.status_code == 409


def test_create_cpo_duplicate_email(client, seeded_config, admin_headers):
    r = client.post(
        "/api/admin/cpos",
        json={
            "username": "newguy",
            "email": "john@example.com",   # already exists
            "team_name": "Sales",
            "initial_password": "securepass",
        },
        headers=admin_headers,
    )
    assert r.status_code == 409


def test_create_cpo_password_too_short(client, seeded_config, admin_headers):
    r = client.post(
        "/api/admin/cpos",
        json={
            "username": "newguy",
            "email": "new@example.com",
            "team_name": "Sales",
            "initial_password": "short",
        },
        headers=admin_headers,
    )
    assert r.status_code == 422


def test_create_cpo_persisted_in_list(client, seeded_config, admin_headers):
    client.post(
        "/api/admin/cpos",
        json={
            "username": "bob",
            "email": "bob@example.com",
            "team_name": "DevOps",
            "initial_password": "password1",
        },
        headers=admin_headers,
    )
    r = client.get("/api/admin/cpos", headers=admin_headers)
    usernames = [c["username"] for c in r.json()]
    assert "bob" in usernames


# ---------------------------------------------------------------------------
# POST /api/admin/cpos/{cpo_id}/reset-password
# ---------------------------------------------------------------------------

def test_reset_password_success(client, seeded_config, admin_headers):
    cpo_id = seeded_config["cpo_id"]
    r = client.post(
        f"/api/admin/cpos/{cpo_id}/reset-password",
        json={"new_password": "newpassword1"},
        headers=admin_headers,
    )
    assert r.status_code == 200
    # verify new password works for login
    login = client.post("/api/auth/login", json={"username": "john", "password": "newpassword1"})
    assert login.status_code == 200


def test_reset_password_not_found(client, seeded_config, admin_headers):
    r = client.post(
        "/api/admin/cpos/nonexistent-id/reset-password",
        json={"new_password": "newpassword1"},
        headers=admin_headers,
    )
    assert r.status_code == 404


def test_reset_password_too_short(client, seeded_config, admin_headers):
    cpo_id = seeded_config["cpo_id"]
    r = client.post(
        f"/api/admin/cpos/{cpo_id}/reset-password",
        json={"new_password": "short"},
        headers=admin_headers,
    )
    assert r.status_code == 422
