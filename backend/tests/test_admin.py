import pytest
from fastapi.testclient import TestClient

from main import app
from tests.conftest import ADMIN_PASSWORD, CPO_PASSWORD, SECOND_ADMIN_PASSWORD


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
    assert r.status_code == 401  # HTTPBearer returns 401 when header missing (FastAPI >= 0.116)


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


def test_create_cpo_password_common(client, seeded_config, admin_headers):
    r = client.post(
        "/api/admin/cpos",
        json={
            "username": "newguy",
            "email": "new@example.com",
            "team_name": "Sales",
            "initial_password": "password",
        },
        headers=admin_headers,
    )
    assert r.status_code == 422
    assert "too common" in r.json()["detail"].lower()


def test_create_cpo_password_contains_username(client, seeded_config, admin_headers):
    r = client.post(
        "/api/admin/cpos",
        json={
            "username": "alice",
            "email": "alice@example.com",
            "team_name": "Sales",
            "initial_password": "myalicepass",
        },
        headers=admin_headers,
    )
    assert r.status_code == 422
    assert "must not contain your username" in r.json()["detail"].lower()


def test_create_cpo_password_contains_forbidden_word(client, seeded_config, admin_headers):
    r = client.post(
        "/api/admin/cpos",
        json={
            "username": "newguy",
            "email": "new@example.com",
            "team_name": "Sales",
            "initial_password": "mycpoapp",
        },
        headers=admin_headers,
    )
    assert r.status_code == 422
    assert "application name" in r.json()["detail"].lower()


def test_create_cpo_persisted_in_list(client, seeded_config, admin_headers):
    client.post(
        "/api/admin/cpos",
        json={
            "username": "bob",
            "email": "bob@example.com",
            "team_name": "DevOps",
            "initial_password": "securepass",
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
        json={"new_password": "newsecurepass"},
        headers=admin_headers,
    )
    assert r.status_code == 200
    # verify new password works for login
    login = client.post("/api/auth/login", json={"username": "john", "password": "newsecurepass"})  # NOSONAR
    assert login.status_code == 200


def test_reset_password_invalidates_old_token(client, seeded_config, admin_headers, cpo_headers):
    """A CPO token issued before a password reset must be rejected afterwards."""
    cpo_id = seeded_config["cpo_id"]
    # Confirm old token still works before reset
    assert client.get("/api/cpo/me", headers=cpo_headers).status_code == 200
    # Reset password
    client.post(
        f"/api/admin/cpos/{cpo_id}/reset-password",
        json={"new_password": "brandnewpass1"},  # NOSONAR
        headers=admin_headers,
    )
    # Old token must now be rejected
    assert client.get("/api/cpo/me", headers=cpo_headers).status_code == 401


def test_reset_password_not_found(client, seeded_config, admin_headers):
    r = client.post(
        "/api/admin/cpos/nonexistent-id/reset-password",
        json={"new_password": "newsecurepass"},
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


def test_reset_password_common(client, seeded_config, admin_headers):
    cpo_id = seeded_config["cpo_id"]
    r = client.post(
        f"/api/admin/cpos/{cpo_id}/reset-password",
        json={"new_password": "password"},
        headers=admin_headers,
    )
    assert r.status_code == 422
    assert "too common" in r.json()["detail"].lower()


def test_reset_password_contains_username(client, seeded_config, admin_headers):
    cpo_id = seeded_config["cpo_id"]
    r = client.post(
        f"/api/admin/cpos/{cpo_id}/reset-password",
        json={"new_password": "myjohnpass"},  # CPO username is "john"
        headers=admin_headers,
    )
    assert r.status_code == 422
    assert "must not contain your username" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# PUT /api/admin/cpos/{cpo_id}
# ---------------------------------------------------------------------------

def test_update_cpo_success(client, seeded_config, admin_headers):
    cpo_id = seeded_config["cpo_id"]
    r = client.put(
        f"/api/admin/cpos/{cpo_id}",
        json={"email": "new@example.com", "team_name": "New Team"},
        headers=admin_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == "new@example.com"
    assert body["team_name"] == "New Team"
    assert body["username"] == "john"   # unchanged


def test_update_cpo_reflected_in_list(client, seeded_config, admin_headers):
    cpo_id = seeded_config["cpo_id"]
    client.put(
        f"/api/admin/cpos/{cpo_id}",
        json={"email": "updated@example.com", "team_name": "Updated"},
        headers=admin_headers,
    )
    cpos = client.get("/api/admin/cpos", headers=admin_headers).json()
    assert cpos[0]["email"] == "updated@example.com"
    assert cpos[0]["team_name"] == "Updated"


def test_update_cpo_duplicate_email(client, seeded_config, admin_headers):
    # Create a second CPO first
    client.post(
        "/api/admin/cpos",
        json={"username": "bob", "email": "bob@example.com",
              "team_name": "DevOps", "initial_password": "securepass"},
        headers=admin_headers,
    )
    cpo_id = seeded_config["cpo_id"]
    r = client.put(
        f"/api/admin/cpos/{cpo_id}",
        json={"email": "bob@example.com", "team_name": "Engineering"},
        headers=admin_headers,
    )
    assert r.status_code == 409


def test_update_cpo_same_email_allowed(client, seeded_config, admin_headers):
    """Updating other fields while keeping the same email should succeed."""
    cpo_id = seeded_config["cpo_id"]
    r = client.put(
        f"/api/admin/cpos/{cpo_id}",
        json={"email": "john@example.com", "team_name": "Different Team"},
        headers=admin_headers,
    )
    assert r.status_code == 200
    assert r.json()["team_name"] == "Different Team"


def test_update_cpo_not_found(client, seeded_config, admin_headers):
    r = client.put(
        "/api/admin/cpos/nonexistent",
        json={"email": "x@example.com", "team_name": "X"},
        headers=admin_headers,
    )
    assert r.status_code == 404


def test_update_cpo_requires_admin(client, seeded_config, cpo_headers):
    cpo_id = seeded_config["cpo_id"]
    r = client.put(
        f"/api/admin/cpos/{cpo_id}",
        json={"email": "x@example.com", "team_name": "X"},
        headers=cpo_headers,
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# DELETE /api/admin/cpos/{cpo_id}
# ---------------------------------------------------------------------------

def test_delete_cpo_success(client, seeded_config, admin_headers):
    cpo_id = seeded_config["cpo_id"]
    r = client.delete(f"/api/admin/cpos/{cpo_id}", headers=admin_headers)
    assert r.status_code == 204
    cpos = client.get("/api/admin/cpos", headers=admin_headers).json()
    assert all(c["id"] != cpo_id for c in cpos)


def test_delete_cpo_cannot_login_after(client, seeded_config, admin_headers):
    cpo_id = seeded_config["cpo_id"]
    client.delete(f"/api/admin/cpos/{cpo_id}", headers=admin_headers)
    r = client.post("/api/auth/login", json={"username": "john", "password": CPO_PASSWORD})
    assert r.status_code == 401


def test_delete_cpo_not_found(client, seeded_config, admin_headers):
    r = client.delete("/api/admin/cpos/nonexistent", headers=admin_headers)
    assert r.status_code == 404


def test_delete_cpo_requires_admin(client, seeded_config, cpo_headers):
    cpo_id = seeded_config["cpo_id"]
    r = client.delete(f"/api/admin/cpos/{cpo_id}", headers=cpo_headers)
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# GET /api/admin/admins
# ---------------------------------------------------------------------------

def test_list_admins_marks_self(client, second_admin, admin_headers):
    r = client.get("/api/admin/admins", headers=admin_headers)
    assert r.status_code == 200
    data = {a["username"]: a for a in r.json()}
    assert data["admin"]["is_self"] is True
    assert data["admin2"]["is_self"] is False
    assert all("password_hash" not in a for a in data.values())


def test_list_admins_is_self_follows_caller(client, second_admin, second_admin_headers):
    r = client.get("/api/admin/admins", headers=second_admin_headers)
    data = {a["username"]: a for a in r.json()}
    assert data["admin"]["is_self"] is False
    assert data["admin2"]["is_self"] is True


def test_list_admins_requires_admin(client, seeded_config, cpo_headers):
    assert client.get("/api/admin/admins", headers=cpo_headers).status_code == 403


def test_list_admins_requires_auth(client, seeded_config):
    assert client.get("/api/admin/admins").status_code == 401


# ---------------------------------------------------------------------------
# POST /api/admin/admins
# ---------------------------------------------------------------------------

def test_create_admin_success(client, seeded_config, admin_headers):
    r = client.post(
        "/api/admin/admins",
        json={"username": "root2", "initial_password": "securepass"},  # NOSONAR
        headers=admin_headers,
    )
    assert r.status_code == 201
    body = r.json()
    assert body["username"] == "root2"
    assert "password_hash" not in body
    # new admin appears in the list and can log in
    usernames = [a["username"] for a in client.get("/api/admin/admins", headers=admin_headers).json()]
    assert "root2" in usernames
    login = client.post("/api/auth/login", json={"username": "root2", "password": "securepass"})  # NOSONAR
    assert login.status_code == 200
    assert login.json()["role"] == "admin"


def test_create_admin_duplicate_username(client, seeded_config, admin_headers):
    r = client.post(
        "/api/admin/admins",
        json={"username": "Admin", "initial_password": "securepass"},  # case-insensitive dup  # NOSONAR
        headers=admin_headers,
    )
    assert r.status_code == 409


def test_create_admin_username_collides_with_cpo(client, seeded_config, admin_headers):
    r = client.post(
        "/api/admin/admins",
        json={"username": "john", "initial_password": "securepass"},  # CPO username  # NOSONAR
        headers=admin_headers,
    )
    assert r.status_code == 409


def test_create_cpo_username_collides_with_admin(client, seeded_config, admin_headers):
    r = client.post(
        "/api/admin/cpos",
        json={"username": "admin", "email": "adm@example.com",
              "team_name": "Ops", "initial_password": "securepass"},  # NOSONAR
        headers=admin_headers,
    )
    assert r.status_code == 409


@pytest.mark.parametrize(
    "password",
    [
        "short",         # < 8 chars (Pydantic)
        "password",      # common
        "myroot2pass",   # contains username
        "mycpoapp",      # forbidden word
    ],
)
def test_create_admin_password_rejected(client, seeded_config, admin_headers, password):
    r = client.post(
        "/api/admin/admins",
        json={"username": "root2", "initial_password": password},
        headers=admin_headers,
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# DELETE /api/admin/admins/{admin_id}
# ---------------------------------------------------------------------------

def test_delete_admin_success(client, second_admin, admin_headers, second_admin_headers):
    r = client.delete(f"/api/admin/admins/{second_admin.id}", headers=admin_headers)
    assert r.status_code == 204
    ids = [a["id"] for a in client.get("/api/admin/admins", headers=admin_headers).json()]
    assert second_admin.id not in ids
    # deleted admin's token no longer works
    assert client.get("/api/admin/admins", headers=second_admin_headers).status_code == 401
    # and the account can no longer log in
    login = client.post(
        "/api/auth/login", json={"username": "admin2", "password": SECOND_ADMIN_PASSWORD}
    )
    assert login.status_code == 401


def test_delete_admin_self_forbidden(client, second_admin, admin_headers):
    r = client.delete("/api/admin/admins/1", headers=admin_headers)
    assert r.status_code == 403


def test_delete_admin_not_found(client, seeded_config, admin_headers):
    r = client.delete("/api/admin/admins/999", headers=admin_headers)
    assert r.status_code == 404


def test_delete_last_admin_rejected(seeded_config):
    """Service-level guard: even a foreign actor cannot remove the last admin."""
    from fastapi import HTTPException
    from services import admin_service

    with pytest.raises(HTTPException) as exc:
        admin_service.delete_admin(actor_id=999, admin_id=1)
    assert exc.value.status_code == 409


def test_delete_admin_requires_admin(client, second_admin, cpo_headers):
    r = client.delete(f"/api/admin/admins/{second_admin.id}", headers=cpo_headers)
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# POST /api/admin/admins/{admin_id}/reset-password
# ---------------------------------------------------------------------------

def test_reset_admin_password_success(client, second_admin, admin_headers, second_admin_headers):
    # target's pre-reset token works
    assert client.get("/api/admin/admins", headers=second_admin_headers).status_code == 200
    r = client.post(
        f"/api/admin/admins/{second_admin.id}/reset-password",
        json={"new_password": "brandnewpass1"},  # NOSONAR
        headers=admin_headers,
    )
    assert r.status_code == 200
    # old token revoked, old password dead, new password works
    assert client.get("/api/admin/admins", headers=second_admin_headers).status_code == 401
    old = client.post("/api/auth/login", json={"username": "admin2", "password": SECOND_ADMIN_PASSWORD})
    assert old.status_code == 401
    new = client.post("/api/auth/login", json={"username": "admin2", "password": "brandnewpass1"})  # NOSONAR
    assert new.status_code == 200


def test_reset_admin_password_self_forbidden(client, seeded_config, admin_headers):
    r = client.post(
        "/api/admin/admins/1/reset-password",
        json={"new_password": "brandnewpass1"},  # NOSONAR
        headers=admin_headers,
    )
    assert r.status_code == 403


def test_reset_admin_password_not_found(client, seeded_config, admin_headers):
    r = client.post(
        "/api/admin/admins/999/reset-password",
        json={"new_password": "brandnewpass1"},  # NOSONAR
        headers=admin_headers,
    )
    assert r.status_code == 404


def test_reset_admin_password_policy_rejected(client, second_admin, admin_headers):
    r = client.post(
        f"/api/admin/admins/{second_admin.id}/reset-password",
        json={"new_password": "password"},  # NOSONAR
        headers=admin_headers,
    )
    assert r.status_code == 422
    assert "too common" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# POST /api/admin/change-password
# ---------------------------------------------------------------------------

def test_change_admin_password_success(client, seeded_config, admin_headers):
    r = client.post(
        "/api/admin/change-password",
        json={"current_password": ADMIN_PASSWORD, "new_password": "freshsecret1"},  # NOSONAR
        headers=admin_headers,
    )
    assert r.status_code == 204
    # the version bump revokes the token used for the change
    assert client.get("/api/admin/admins", headers=admin_headers).status_code == 401
    # old password dead, new password works
    assert client.post(
        "/api/auth/login", json={"username": "admin", "password": ADMIN_PASSWORD}
    ).status_code == 401
    assert client.post(
        "/api/auth/login", json={"username": "admin", "password": "freshsecret1"}  # NOSONAR
    ).status_code == 200


def test_change_admin_password_wrong_current(client, seeded_config, admin_headers):
    r = client.post(
        "/api/admin/change-password",
        json={"current_password": "wrongpass", "new_password": "freshsecret1"},  # NOSONAR
        headers=admin_headers,
    )
    assert r.status_code == 401
    # password unchanged
    assert client.post(
        "/api/auth/login", json={"username": "admin", "password": ADMIN_PASSWORD}
    ).status_code == 200


@pytest.mark.parametrize("password", ["short", "password", "myadminpass"])
def test_change_admin_password_policy_rejected(client, seeded_config, admin_headers, password):
    r = client.post(
        "/api/admin/change-password",
        json={"current_password": ADMIN_PASSWORD, "new_password": password},
        headers=admin_headers,
    )
    assert r.status_code == 422


def test_change_admin_password_requires_admin(client, seeded_config, cpo_headers):
    r = client.post(
        "/api/admin/change-password",
        json={"current_password": "x", "new_password": "freshsecret1"},  # NOSONAR
        headers=cpo_headers,
    )
    assert r.status_code == 403
