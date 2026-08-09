from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient

import storage
from main import app
from models import SessionFile
from utils import new_id
from tests.conftest import ADMIN_PASSWORD, CPO_PASSWORD, SECOND_ADMIN_PASSWORD


# All fixtures come from conftest.py (client, seeded_config, admin_headers, cpo_headers,
# second_team_member, second_team_member_headers)


# ---------------------------------------------------------------------------
# GET /api/admin/cpos
# ---------------------------------------------------------------------------

def test_list_cpos_returns_seeded_cpo(client, seeded_config, admin_headers):
    r = client.get("/api/admin/cpos", headers=admin_headers)
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["team_name"] == "Engineering"
    assert data[0]["team_id"] == seeded_config["team_id"]
    members = data[0]["members"]
    assert len(members) == 1
    assert members[0]["username"] == "john"
    assert "password_hash" not in members[0]


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
    assert body["team_name"] == "Marketing"
    assert "team_id" in body
    assert "unique_link" in body
    assert len(body["unique_link"]) >= 16
    assert len(body["members"]) == 1
    assert body["members"][0]["username"] == "alice"
    assert "id" not in body   # top-level id is gone; it's team_id now


def test_create_cpo_password_over_72_bytes(client, seeded_config, admin_headers):
    """A password longer than bcrypt's 72-byte limit is accepted and remains
    verifiable at login (regression: bcrypt 5 raises instead of silently
    truncating on hash/verify)."""
    long_password = "Xk7Qm2Vt9Zr4Wb" * 6
    assert len(long_password.encode()) > 72
    r = client.post(
        "/api/admin/cpos",
        json={
            "username": "longpw",
            "email": "longpw@example.com",
            "team_name": "Ops",
            "initial_password": long_password,
        },
        headers=admin_headers,
    )
    assert r.status_code == 201
    login = client.post(
        "/api/auth/login",
        json={"username": "longpw", "password": long_password},
    )
    assert login.status_code == 200


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
    usernames = [m["username"] for t in r.json() for m in t["members"]]
    assert "bob" in usernames


def test_create_cpo_always_creates_new_team(client, seeded_config, admin_headers):
    """POST /api/admin/cpos has no way to attach a login to an existing team —
    every call creates a brand new team plus its first login. Adding a peer
    to an EXISTING team is only possible via a self-service invite (see
    test_team.py)."""
    r = client.post(
        "/api/admin/cpos",
        json={
            "username": "newperson",
            "email": "newperson@example.com",
            "team_name": "Engineering",   # same name as seeded team, on purpose
            "initial_password": "securepass",
        },
        headers=admin_headers,
    )
    assert r.status_code == 201
    body = r.json()
    assert body["team_id"] != seeded_config["team_id"]
    assert body["members"][0]["id"] != seeded_config["cpo_id"]
    listing = client.get("/api/admin/cpos", headers=admin_headers).json()
    assert len(listing) == 2   # two distinct teams, not one team with two members


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
    assert r.json()["username"] == "john"
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
# PUT /api/admin/cpos/{cpo_id}  (email only — team_name moved to /admin/teams/{id})
# ---------------------------------------------------------------------------

def test_update_cpo_email_success(client, seeded_config, admin_headers):
    cpo_id = seeded_config["cpo_id"]
    r = client.put(
        f"/api/admin/cpos/{cpo_id}",
        json={"email": "new@example.com"},
        headers=admin_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == "new@example.com"
    assert body["username"] == "john"   # unchanged
    assert "team_name" not in body      # TeamMemberResponse has no team fields


def test_update_cpo_email_reflected_in_list(client, seeded_config, admin_headers):
    cpo_id = seeded_config["cpo_id"]
    client.put(
        f"/api/admin/cpos/{cpo_id}",
        json={"email": "updated@example.com"},
        headers=admin_headers,
    )
    listing = client.get("/api/admin/cpos", headers=admin_headers).json()
    member = listing[0]["members"][0]
    assert member["email"] == "updated@example.com"


def test_update_cpo_email_duplicate(client, seeded_config, admin_headers):
    # Create a second CPO (own team) first
    client.post(
        "/api/admin/cpos",
        json={"username": "bob", "email": "bob@example.com",
              "team_name": "DevOps", "initial_password": "securepass"},
        headers=admin_headers,
    )
    cpo_id = seeded_config["cpo_id"]
    r = client.put(
        f"/api/admin/cpos/{cpo_id}",
        json={"email": "bob@example.com"},
        headers=admin_headers,
    )
    assert r.status_code == 409


def test_update_cpo_email_same_allowed(client, seeded_config, admin_headers):
    """Updating to the same email should succeed (no false-positive duplicate)."""
    cpo_id = seeded_config["cpo_id"]
    r = client.put(
        f"/api/admin/cpos/{cpo_id}",
        json={"email": "john@example.com"},
        headers=admin_headers,
    )
    assert r.status_code == 200


def test_update_cpo_email_not_found(client, seeded_config, admin_headers):
    r = client.put(
        "/api/admin/cpos/nonexistent",
        json={"email": "x@example.com"},
        headers=admin_headers,
    )
    assert r.status_code == 404


def test_update_cpo_email_requires_admin(client, seeded_config, cpo_headers):
    cpo_id = seeded_config["cpo_id"]
    r = client.put(
        f"/api/admin/cpos/{cpo_id}",
        json={"email": "x@example.com"},
        headers=cpo_headers,
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# PUT /api/admin/teams/{team_id}
# ---------------------------------------------------------------------------

def test_update_team_name_success(client, seeded_config, admin_headers):
    team_id = seeded_config["team_id"]
    r = client.put(
        f"/api/admin/teams/{team_id}",
        json={"team_name": "New Team"},
        headers=admin_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["team_name"] == "New Team"
    assert body["team_id"] == team_id
    assert body["members"][0]["username"] == "john"


def test_update_team_name_reflected_in_list(client, seeded_config, admin_headers):
    team_id = seeded_config["team_id"]
    client.put(f"/api/admin/teams/{team_id}", json={"team_name": "Renamed"}, headers=admin_headers)
    listing = client.get("/api/admin/cpos", headers=admin_headers).json()
    team = next(t for t in listing if t["team_id"] == team_id)
    assert team["team_name"] == "Renamed"


def test_update_team_name_rejects_empty(client, seeded_config, admin_headers):
    team_id = seeded_config["team_id"]
    r = client.put(f"/api/admin/teams/{team_id}", json={"team_name": ""}, headers=admin_headers)
    assert r.status_code == 422


def test_update_team_name_not_found(client, seeded_config, admin_headers):
    r = client.put("/api/admin/teams/nonexistent", json={"team_name": "X"}, headers=admin_headers)
    assert r.status_code == 404


def test_update_team_name_requires_admin(client, seeded_config, cpo_headers):
    team_id = seeded_config["team_id"]
    r = client.put(f"/api/admin/teams/{team_id}", json={"team_name": "X"}, headers=cpo_headers)
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# DELETE /api/admin/cpos/{cpo_id}
# ---------------------------------------------------------------------------

def test_delete_cpo_success(client, seeded_config, admin_headers):
    cpo_id = seeded_config["cpo_id"]
    r = client.delete(f"/api/admin/cpos/{cpo_id}", headers=admin_headers)
    assert r.status_code == 204
    listing = client.get("/api/admin/cpos", headers=admin_headers).json()
    assert all(t["team_id"] != seeded_config["team_id"] for t in listing)


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


def test_delete_last_login_cascades_menus_and_sessions(client, seeded_config, admin_headers):
    """Deleting the ONLY login on a team also deletes the team, and with it
    (via the teams.id FK ON DELETE CASCADE) its menus and sessions."""
    team_id = seeded_config["team_id"]
    storage.create_menu(team_id, "Default")
    session = SessionFile(
        id=new_id(),
        team_id=team_id,
        team_name="Engineering",
        session_date=date(2099, 1, 1),
        start_time="11:00",
        end_time="12:00",
        created_at=datetime.now(tz=timezone.utc),
    )
    storage.save_session(session)
    assert storage.list_menus(team_id) != []
    assert storage.list_sessions(team_id) != []

    r = client.delete(f"/api/admin/cpos/{seeded_config['cpo_id']}", headers=admin_headers)
    assert r.status_code == 204

    assert storage.list_menus(team_id) == []
    assert storage.list_sessions(team_id) == []
    team_ids = [t["team_id"] for t in client.get("/api/admin/cpos", headers=admin_headers).json()]
    assert team_id not in team_ids


def test_delete_one_of_two_logins_leaves_team_intact(
    client, seeded_config, second_team_member, admin_headers
):
    """Deleting one of TWO logins on a team leaves the team's data (and the
    team itself) intact — only the removed login disappears."""
    team_id = seeded_config["team_id"]
    storage.create_menu(team_id, "Default")

    r = client.delete(f"/api/admin/cpos/{second_team_member.id}", headers=admin_headers)
    assert r.status_code == 204

    listing = client.get("/api/admin/cpos", headers=admin_headers).json()
    team = next(t for t in listing if t["team_id"] == team_id)
    assert [m["username"] for m in team["members"]] == ["john"]
    assert storage.list_menus(team_id) != []


# ---------------------------------------------------------------------------
# GET /api/admin/me and PATCH /api/admin/language
# ---------------------------------------------------------------------------

def test_get_admin_me_returns_profile(client, seeded_config, admin_headers):
    r = client.get("/api/admin/me", headers=admin_headers)
    assert r.status_code == 200
    assert r.json() == {"id": 1, "username": "admin", "language": None}


def test_get_admin_me_requires_admin(client, seeded_config, cpo_headers):
    assert client.get("/api/admin/me", headers=cpo_headers).status_code == 403


def test_get_admin_me_requires_auth(client, seeded_config):
    assert client.get("/api/admin/me").status_code == 401


@pytest.mark.parametrize("tag", ["en", "de-CH", "fr-CH", "it-CH"])
def test_update_admin_language_round_trips(client, seeded_config, admin_headers, tag):
    r = client.patch("/api/admin/language", json={"language": tag}, headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["language"] == tag
    assert client.get("/api/admin/me", headers=admin_headers).json()["language"] == tag


def test_update_admin_language_null_clears_preference(client, seeded_config, admin_headers):
    client.patch("/api/admin/language", json={"language": "it-CH"}, headers=admin_headers)
    r = client.patch("/api/admin/language", json={"language": None}, headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["language"] is None
    assert client.get("/api/admin/me", headers=admin_headers).json()["language"] is None


def test_update_admin_language_rejects_unsupported_tag(client, seeded_config, admin_headers):
    r = client.patch("/api/admin/language", json={"language": "de-DE"}, headers=admin_headers)
    assert r.status_code == 422


def test_update_admin_language_is_per_admin(
    client, second_admin, admin_headers, second_admin_headers
):
    client.patch("/api/admin/language", json={"language": "de-CH"}, headers=admin_headers)
    assert client.get("/api/admin/me", headers=second_admin_headers).json()["language"] is None


def test_update_admin_language_requires_admin(client, seeded_config, cpo_headers):
    r = client.patch("/api/admin/language", json={"language": "de-CH"}, headers=cpo_headers)
    assert r.status_code == 403


def test_update_admin_language_requires_auth(client, seeded_config):
    assert client.patch("/api/admin/language", json={"language": "de-CH"}).status_code == 401


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
