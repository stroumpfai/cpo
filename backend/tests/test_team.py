"""
Tests for self-service team member + invite management:
  GET/DELETE  /api/cpo/team-members[...]
  GET/POST/DELETE /api/cpo/team-invites[...]
  GET/POST    /api/join/{token}

All CPO logins on a team are equal peers — no owner/deputy hierarchy. See
services/team_service.py.
"""
from datetime import datetime, timedelta, timezone

import pytest

import storage
from config import TEAM_INVITE_EXPIRY_HOURS
from models import CPORecord, TeamInvite, TeamRecord
from security import create_token
from utils import generate_link, hash_password, new_id

# Fixtures from conftest.py: client, seeded_config, cpo_headers,
# second_team_member, second_team_member_headers, admin_headers


MARY_PASSWORD = "DesignTeamPass88"  # NOSONAR


def _mary_headers(client, admin_headers) -> tuple[dict, str]:
    """Create a CPO login on a brand-new (different) team — the cross-team
    isolation counterpart used throughout test_cpo.py."""
    create = client.post(
        "/api/admin/cpos",
        json={
            "username": "mary",
            "email": "mary@example.com",
            "team_name": "Design",
            "initial_password": MARY_PASSWORD,
        },
        headers=admin_headers,
    )
    assert create.status_code == 201
    body = create.json()
    mary_login_id = body["members"][0]["id"]
    headers = {"Authorization": f"Bearer {create_token(mary_login_id, 'cpo')}"}
    return headers, body["team_id"]


# ---------------------------------------------------------------------------
# GET /api/cpo/team-members
# ---------------------------------------------------------------------------

def test_list_team_members_seeded_alone(client, seeded_config, cpo_headers):
    r = client.get("/api/cpo/team-members", headers=cpo_headers)
    assert r.status_code == 200
    members = r.json()
    assert len(members) == 1
    assert members[0]["username"] == "john"
    assert members[0]["is_self"] is True


def test_list_team_members_shows_both_after_second_joins(
    client, seeded_config, second_team_member, cpo_headers, second_team_member_headers
):
    r = client.get("/api/cpo/team-members", headers=cpo_headers)
    usernames = {m["username"] for m in r.json()}
    assert usernames == {"john", "jane"}

    # is_self follows the caller, not a fixed member
    as_john = {m["username"]: m["is_self"] for m in client.get("/api/cpo/team-members", headers=cpo_headers).json()}
    assert as_john == {"john": True, "jane": False}

    as_jane = {
        m["username"]: m["is_self"]
        for m in client.get("/api/cpo/team-members", headers=second_team_member_headers).json()
    }
    assert as_jane == {"john": False, "jane": True}


def test_list_team_members_requires_cpo(client, seeded_config, admin_headers):
    r = client.get("/api/cpo/team-members", headers=admin_headers)
    assert r.status_code == 403


def test_list_team_members_requires_auth(client, seeded_config):
    r = client.get("/api/cpo/team-members")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# DELETE /api/cpo/team-members/{member_id}
# ---------------------------------------------------------------------------

def test_remove_team_member_succeeds_with_two_members(
    client, seeded_config, second_team_member, cpo_headers
):
    r = client.delete(f"/api/cpo/team-members/{second_team_member.id}", headers=cpo_headers)
    assert r.status_code == 204
    remaining = client.get("/api/cpo/team-members", headers=cpo_headers).json()
    assert [m["username"] for m in remaining] == ["john"]


def test_removed_member_cannot_authenticate_after(
    client, seeded_config, second_team_member, second_team_member_headers, cpo_headers
):
    # Confirm the token works before removal
    assert client.get("/api/cpo/team-members", headers=second_team_member_headers).status_code == 200
    client.delete(f"/api/cpo/team-members/{second_team_member.id}", headers=cpo_headers)
    # The removed login's row is gone entirely — require_cpo revokes it
    r = client.get("/api/cpo/team-members", headers=second_team_member_headers)
    assert r.status_code == 401


def test_remove_last_member_returns_409(client, seeded_config, cpo_headers):
    r = client.delete(f"/api/cpo/team-members/{seeded_config['cpo_id']}", headers=cpo_headers)
    assert r.status_code == 409


def test_remove_unknown_member_returns_404(client, seeded_config, cpo_headers):
    r = client.delete("/api/cpo/team-members/nonexistent", headers=cpo_headers)
    assert r.status_code == 404


def test_remove_member_from_other_team_returns_404(
    client, seeded_config, second_team_member, cpo_headers, admin_headers
):
    """A CPO from a different team cannot remove a member of another team."""
    mary_headers, _mary_team_id = _mary_headers(client, admin_headers)
    r = client.delete(f"/api/cpo/team-members/{seeded_config['cpo_id']}", headers=mary_headers)
    assert r.status_code == 404
    # john's team is untouched
    remaining = client.get("/api/cpo/team-members", headers=cpo_headers).json()
    assert {m["username"] for m in remaining} == {"john", "jane"}


def test_remove_team_member_requires_cpo(client, seeded_config, second_team_member, admin_headers):
    r = client.delete(f"/api/cpo/team-members/{second_team_member.id}", headers=admin_headers)
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# POST /api/cpo/team-members/{member_id}/reset-password
# ---------------------------------------------------------------------------

def test_reset_teammate_password_succeeds(
    client, seeded_config, second_team_member, cpo_headers
):
    r = client.post(
        f"/api/cpo/team-members/{second_team_member.id}/reset-password",
        json={"new_password": "BrandNewPass123"},  # NOSONAR
        headers=cpo_headers,
    )
    assert r.status_code == 200
    assert r.json()["username"] == "jane"

    old = client.post("/api/auth/login", json={"username": "jane", "password": "teammate123"})
    assert old.status_code == 401
    new = client.post("/api/auth/login", json={"username": "jane", "password": "BrandNewPass123"})  # NOSONAR
    assert new.status_code == 200


def test_reset_teammate_password_unknown_member_404(client, seeded_config, cpo_headers):
    r = client.post(
        "/api/cpo/team-members/nonexistent/reset-password",
        json={"new_password": "BrandNewPass123"},  # NOSONAR
        headers=cpo_headers,
    )
    assert r.status_code == 404


def test_reset_teammate_password_cross_team_404(
    client, seeded_config, cpo_headers, admin_headers
):
    mary_headers, _ = _mary_headers(client, admin_headers)
    r = client.post(
        f"/api/cpo/team-members/{seeded_config['cpo_id']}/reset-password",
        json={"new_password": "BrandNewPass123"},  # NOSONAR
        headers=mary_headers,
    )
    assert r.status_code == 404


def test_reset_teammate_password_policy_rejected(
    client, seeded_config, second_team_member, cpo_headers
):
    r = client.post(
        f"/api/cpo/team-members/{second_team_member.id}/reset-password",
        json={"new_password": "password"},
        headers=cpo_headers,
    )
    assert r.status_code == 422


def test_reset_teammate_password_requires_cpo(client, seeded_config, second_team_member, admin_headers):
    r = client.post(
        f"/api/cpo/team-members/{second_team_member.id}/reset-password",
        json={"new_password": "BrandNewPass123"},  # NOSONAR
        headers=admin_headers,
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# GET/POST /api/cpo/team-invites, DELETE /api/cpo/team-invites/{id}
# ---------------------------------------------------------------------------

def test_create_invite_returns_token_and_expiry(client, seeded_config, cpo_headers):
    before = datetime.now(tz=timezone.utc)
    r = client.post("/api/cpo/team-invites", headers=cpo_headers)
    assert r.status_code == 201
    body = r.json()
    assert len(body["token"]) >= 16
    expires_at = datetime.fromisoformat(body["expires_at"])
    expected = before + timedelta(hours=TEAM_INVITE_EXPIRY_HOURS)
    assert abs((expires_at - expected).total_seconds()) < 60


def test_list_invites_shows_pending(client, seeded_config, cpo_headers):
    create = client.post("/api/cpo/team-invites", headers=cpo_headers)
    token = create.json()["token"]
    r = client.get("/api/cpo/team-invites", headers=cpo_headers)
    assert r.status_code == 200
    tokens = [i["token"] for i in r.json()]
    assert token in tokens


def test_revoke_invite_removes_it(client, seeded_config, cpo_headers):
    create = client.post("/api/cpo/team-invites", headers=cpo_headers)
    invite_id = create.json()["id"]
    r = client.delete(f"/api/cpo/team-invites/{invite_id}", headers=cpo_headers)
    assert r.status_code == 204
    remaining = client.get("/api/cpo/team-invites", headers=cpo_headers).json()
    assert all(i["id"] != invite_id for i in remaining)


def test_revoke_invite_twice_returns_404(client, seeded_config, cpo_headers):
    create = client.post("/api/cpo/team-invites", headers=cpo_headers)
    invite_id = create.json()["id"]
    assert client.delete(f"/api/cpo/team-invites/{invite_id}", headers=cpo_headers).status_code == 204
    r = client.delete(f"/api/cpo/team-invites/{invite_id}", headers=cpo_headers)
    assert r.status_code == 404


def test_revoked_invite_cannot_be_used_to_join(client, seeded_config, cpo_headers):
    create = client.post("/api/cpo/team-invites", headers=cpo_headers)
    token = create.json()["token"]
    invite_id = create.json()["id"]
    client.delete(f"/api/cpo/team-invites/{invite_id}", headers=cpo_headers)

    r = client.get(f"/api/join/{token}")
    assert r.status_code == 404

    r = client.post(
        f"/api/join/{token}",
        json={"username": "newbie", "email": "newbie@example.com", "password": "FreshJoinPass99"},
    )
    assert r.status_code == 404


def test_unknown_token_cannot_be_used(client, seeded_config):
    assert client.get("/api/join/no-such-token").status_code == 404
    r = client.post(
        "/api/join/no-such-token",
        json={"username": "newbie", "email": "newbie@example.com", "password": "FreshJoinPass99"},
    )
    assert r.status_code == 404


def test_list_invites_requires_cpo(client, seeded_config, admin_headers):
    assert client.get("/api/cpo/team-invites", headers=admin_headers).status_code == 403


def test_create_invite_requires_cpo(client, seeded_config, admin_headers):
    assert client.post("/api/cpo/team-invites", headers=admin_headers).status_code == 403


# ---------------------------------------------------------------------------
# GET/POST /api/join/{token}
# ---------------------------------------------------------------------------

def test_get_join_info_returns_team_name(client, seeded_config, cpo_headers):
    create = client.post("/api/cpo/team-invites", headers=cpo_headers)
    token = create.json()["token"]
    r = client.get(f"/api/join/{token}")
    assert r.status_code == 200
    assert r.json()["team_name"] == "Engineering"


def test_get_join_info_unknown_token_404(client, seeded_config):
    r = client.get("/api/join/no-such-token")
    assert r.status_code == 404


def test_join_creates_new_cpo_with_working_token(client, seeded_config, seeded_menu, cpo_headers):
    create = client.post("/api/cpo/team-invites", headers=cpo_headers)
    token = create.json()["token"]

    r = client.post(
        f"/api/join/{token}",
        json={"username": "newbie", "email": "newbie@example.com", "password": "FreshJoinPass99"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "cpo"
    new_headers = {"Authorization": f"Bearer {body['token']}"}

    # the new login can see the team's existing data
    me = client.get("/api/cpo/me", headers=new_headers).json()
    assert me["team_id"] == seeded_config["team_id"]
    assert me["username"] == "newbie"
    menus = client.get("/api/cpo/menus", headers=new_headers).json()
    assert [m["id"] for m in menus] == [seeded_menu.id]

    members = {m["username"] for m in client.get("/api/cpo/team-members", headers=cpo_headers).json()}
    assert members == {"john", "newbie"}


def test_join_token_is_single_use(client, seeded_config, cpo_headers):
    create = client.post("/api/cpo/team-invites", headers=cpo_headers)
    token = create.json()["token"]
    body = {"username": "newbie", "email": "newbie@example.com", "password": "FreshJoinPass99"}

    first = client.post(f"/api/join/{token}", json=body)
    assert first.status_code == 200

    second = client.post(
        f"/api/join/{token}",
        json={"username": "other", "email": "other@example.com", "password": "AltMemberPass1"},
    )
    # _valid_invite_or_404 sees used_at already set on the second attempt —
    # see services/team_service.py:redeem_invite.
    assert second.status_code == 404


def test_join_duplicate_username_returns_409(client, seeded_config, cpo_headers):
    create = client.post("/api/cpo/team-invites", headers=cpo_headers)
    token = create.json()["token"]
    r = client.post(
        f"/api/join/{token}",
        json={"username": "john", "email": "someoneelse@example.com", "password": "SomePass1234"},
    )
    assert r.status_code == 409


def test_join_duplicate_email_returns_409(client, seeded_config, cpo_headers):
    create = client.post("/api/cpo/team-invites", headers=cpo_headers)
    token = create.json()["token"]
    r = client.post(
        f"/api/join/{token}",
        json={"username": "someoneelse", "email": "john@example.com", "password": "SomePass1234"},
    )
    assert r.status_code == 409


def test_join_weak_password_rejected(client, seeded_config, cpo_headers):
    create = client.post("/api/cpo/team-invites", headers=cpo_headers)
    token = create.json()["token"]
    r = client.post(
        f"/api/join/{token}",
        json={"username": "newbie", "email": "newbie@example.com", "password": "password"},
    )
    assert r.status_code == 422


def _expired_invite(seeded_config) -> str:
    """Insert an already-expired invite directly via storage — bypasses the
    24h wait needed to observe real expiry."""
    invite = TeamInvite(
        id=new_id(),
        team_id=seeded_config["team_id"],
        token=generate_link(),
        created_by_cpo_id=seeded_config["cpo_id"],
        created_at=datetime.now(tz=timezone.utc) - timedelta(hours=25),
        expires_at=datetime.now(tz=timezone.utc) - timedelta(hours=1),
    )
    storage.create_invite(invite)
    return invite.token


def test_expired_invite_get_returns_404(client, seeded_config):
    token = _expired_invite(seeded_config)
    assert client.get(f"/api/join/{token}").status_code == 404


def test_expired_invite_post_returns_404(client, seeded_config):
    token = _expired_invite(seeded_config)
    r = client.post(
        f"/api/join/{token}",
        json={"username": "newbie", "email": "newbie@example.com", "password": "FreshJoinPass99"},
    )
    assert r.status_code == 404


def test_expired_invite_excluded_from_pending_list(client, seeded_config, cpo_headers):
    _expired_invite(seeded_config)
    r = client.get("/api/cpo/team-invites", headers=cpo_headers)
    assert r.json() == []
