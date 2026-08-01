from datetime import date, datetime, timedelta, timezone

def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc).replace(tzinfo=None)
from unittest.mock import patch

import pytest

import storage
from main import app
from models import Order, SessionFile
from utils import new_id

# All fixtures come from conftest.py

# Always use a date far in the future so sessions are "upcoming" regardless of
# when the test suite is run.
_FUTURE = (date.today() + timedelta(days=365)).isoformat()


# ---------------------------------------------------------------------------
# GET /api/cpo/me
# ---------------------------------------------------------------------------

def test_get_me(client, seeded_config, cpo_headers):
    r = client.get("/api/cpo/me", headers=cpo_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["username"] == "john"
    assert body["team_name"] == "Engineering"
    assert "unique_link" in body


def test_get_me_requires_cpo(client, seeded_config, admin_headers):
    r = client.get("/api/cpo/me", headers=admin_headers)
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# POST /api/cpo/change-password
# ---------------------------------------------------------------------------

def test_change_password_success(client, seeded_config, cpo_headers):
    """CPO can change password with valid current + strong new."""
    from tests.conftest import CPO_PASSWORD
    r = client.post(
        "/api/cpo/change-password",
        json={
            "current_password": CPO_PASSWORD,
            "new_password": "NewSecurePass123",
        },
        headers=cpo_headers,
    )
    assert r.status_code == 204
    # Verify new password works for login
    login = client.post(
        "/api/auth/login",
        json={"username": "john", "password": "NewSecurePass123"},
    )
    assert login.status_code == 200


def test_change_password_over_72_bytes(client, seeded_config, cpo_headers):
    """A new password longer than bcrypt's 72-byte limit is accepted and
    remains verifiable at login (regression: bcrypt 5 raises instead of
    silently truncating on hash/verify)."""
    from tests.conftest import CPO_PASSWORD
    long_password = "Xk7Qm2Vt9Zr4Wb" * 6
    assert len(long_password.encode()) > 72
    r = client.post(
        "/api/cpo/change-password",
        json={
            "current_password": CPO_PASSWORD,
            "new_password": long_password,
        },
        headers=cpo_headers,
    )
    assert r.status_code == 204
    login = client.post(
        "/api/auth/login",
        json={"username": "john", "password": long_password},
    )
    assert login.status_code == 200


def test_change_password_wrong_current(client, seeded_config, cpo_headers):
    """Wrong current password → 401."""
    r = client.post(
        "/api/cpo/change-password",
        json={
            "current_password": "wrongpassword",
            "new_password": "NewSecurePass123",
        },
        headers=cpo_headers,
    )
    assert r.status_code == 401
    assert "incorrect" in r.json()["detail"].lower()


def test_change_password_weak_new(client, seeded_config, cpo_headers):
    """Weak new password (common) → 422."""
    from tests.conftest import CPO_PASSWORD
    r = client.post(
        "/api/cpo/change-password",
        json={
            "current_password": CPO_PASSWORD,
            "new_password": "password",
        },
        headers=cpo_headers,
    )
    assert r.status_code == 422
    assert "too common" in r.json()["detail"].lower()


def test_change_password_new_contains_username(client, seeded_config, cpo_headers):
    """New password contains username → 422."""
    from tests.conftest import CPO_PASSWORD
    r = client.post(
        "/api/cpo/change-password",
        json={
            "current_password": CPO_PASSWORD,
            "new_password": "myjohnpass",  # CPO username is "john"
        },
        headers=cpo_headers,
    )
    assert r.status_code == 422
    assert "must not contain your username" in r.json()["detail"].lower()


def test_change_password_invalidates_old_token(client, seeded_config, cpo_headers):
    """After change_password, old token is invalidated (token_version bumped)."""
    from tests.conftest import CPO_PASSWORD
    # Confirm token works before change
    assert client.get("/api/cpo/me", headers=cpo_headers).status_code == 200
    # Change password
    client.post(
        "/api/cpo/change-password",
        json={
            "current_password": CPO_PASSWORD,
            "new_password": "NewSecurePass456",
        },
        headers=cpo_headers,
    )
    # Old token must now be rejected
    assert client.get("/api/cpo/me", headers=cpo_headers).status_code == 401


def test_change_password_requires_cpo(client, seeded_config, admin_headers):
    """Admin token cannot use CPO endpoint."""
    r = client.post(
        "/api/cpo/change-password",
        json={
            "current_password": "adminpass",
            "new_password": "NewSecurePass123",
        },
        headers=admin_headers,
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# PATCH /api/cpo/currency
# ---------------------------------------------------------------------------

def test_get_me_includes_currency(client, seeded_config, cpo_headers):
    r = client.get("/api/cpo/me", headers=cpo_headers)
    assert r.status_code == 200
    assert r.json()["currency"] == "CHF"


def test_update_currency_success(client, seeded_config, cpo_headers):
    r = client.patch("/api/cpo/currency", json={"currency": "€"}, headers=cpo_headers)
    assert r.status_code == 200
    assert r.json()["currency"] == "€"


def test_update_currency_reflected_in_get_me(client, seeded_config, cpo_headers):
    client.patch("/api/cpo/currency", json={"currency": "NOK"}, headers=cpo_headers)
    r = client.get("/api/cpo/me", headers=cpo_headers)
    assert r.json()["currency"] == "NOK"


def test_update_currency_rejects_empty(client, seeded_config, cpo_headers):
    r = client.patch("/api/cpo/currency", json={"currency": ""}, headers=cpo_headers)
    assert r.status_code == 422


def test_update_currency_rejects_too_long(client, seeded_config, cpo_headers):
    r = client.patch("/api/cpo/currency", json={"currency": "TOOLONGVALUE"}, headers=cpo_headers)
    assert r.status_code == 422


def test_update_currency_requires_cpo(client, seeded_config, admin_headers):
    r = client.patch("/api/cpo/currency", json={"currency": "€"}, headers=admin_headers)
    assert r.status_code == 403


def test_update_currency_requires_auth(client, seeded_config):
    r = client.patch("/api/cpo/currency", json={"currency": "€"})
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# PATCH /api/cpo/member-identifier
# ---------------------------------------------------------------------------

def test_get_me_includes_member_identifier(client, seeded_config, cpo_headers):
    r = client.get("/api/cpo/me", headers=cpo_headers)
    assert r.status_code == 200
    assert r.json()["member_identifier"] == "name"


def test_update_member_identifier_to_email_success(client, seeded_config, cpo_headers):
    r = client.patch(
        "/api/cpo/member-identifier", json={"member_identifier": "email"}, headers=cpo_headers
    )
    assert r.status_code == 200
    assert r.json()["member_identifier"] == "email"


def test_update_member_identifier_reflected_in_get_me(client, seeded_config, cpo_headers):
    client.patch(
        "/api/cpo/member-identifier", json={"member_identifier": "email"}, headers=cpo_headers
    )
    r = client.get("/api/cpo/me", headers=cpo_headers)
    assert r.json()["member_identifier"] == "email"


def test_update_member_identifier_back_to_name(client, seeded_config, cpo_headers):
    client.patch(
        "/api/cpo/member-identifier", json={"member_identifier": "email"}, headers=cpo_headers
    )
    r = client.patch(
        "/api/cpo/member-identifier", json={"member_identifier": "name"}, headers=cpo_headers
    )
    assert r.status_code == 200
    assert r.json()["member_identifier"] == "name"


def test_update_member_identifier_rejects_unknown_value(client, seeded_config, cpo_headers):
    r = client.patch(
        "/api/cpo/member-identifier", json={"member_identifier": "phone"}, headers=cpo_headers
    )
    assert r.status_code == 422


def test_update_member_identifier_requires_cpo(client, seeded_config, admin_headers):
    r = client.patch(
        "/api/cpo/member-identifier", json={"member_identifier": "email"}, headers=admin_headers
    )
    assert r.status_code == 403


def test_update_member_identifier_requires_auth(client, seeded_config):
    r = client.patch("/api/cpo/member-identifier", json={"member_identifier": "email"})
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Settings fields are independent (no lost updates)
#
# The settings page PATCHes team name, currency and member identifier in
# parallel. These used to load-modify-save the whole config, so whichever
# request committed last reverted the other two to its own stale snapshot.
# ---------------------------------------------------------------------------

def test_settings_updates_do_not_clobber_each_other(client, seeded_config, cpo_headers):
    """Each PATCH must leave the other settings columns untouched."""
    client.patch("/api/cpo/member-identifier", json={"member_identifier": "email"}, headers=cpo_headers)
    client.patch("/api/cpo/currency", json={"currency": "EUR"}, headers=cpo_headers)
    client.patch("/api/cpo/team-name", json={"team_name": "Platform"}, headers=cpo_headers)

    me = client.get("/api/cpo/me", headers=cpo_headers).json()
    assert me["member_identifier"] == "email"
    assert me["currency"] == "EUR"
    assert me["team_name"] == "Platform"


def test_concurrent_settings_updates_all_persist(client, seeded_config, cpo_headers):
    """Parallel PATCHes to different settings fields must all survive."""
    import concurrent.futures

    calls = [
        ("/api/cpo/team-name", {"team_name": "Platform"}),
        ("/api/cpo/currency", {"currency": "EUR"}),
        ("/api/cpo/member-identifier", {"member_identifier": "email"}),
    ]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        results = [
            f.result()
            for f in [pool.submit(client.patch, path, json=body, headers=cpo_headers) for path, body in calls]
        ]
    assert all(r.status_code == 200 for r in results)

    me = client.get("/api/cpo/me", headers=cpo_headers).json()
    assert me["member_identifier"] == "email"
    assert me["currency"] == "EUR"
    assert me["team_name"] == "Platform"


def test_update_setting_on_missing_cpo_returns_404(client, seeded_config):
    """A token for a deleted CPO must 404, not silently no-op."""
    from security import create_token

    headers = {"Authorization": f"Bearer {create_token('no-such-cpo-id', 'cpo')}"}
    r = client.patch("/api/cpo/currency", json={"currency": "EUR"}, headers=headers)
    assert r.status_code in (401, 404)


# ---------------------------------------------------------------------------
# PATCH /api/cpo/team-name
# ---------------------------------------------------------------------------

def test_get_me_includes_team_name(client, seeded_config, cpo_headers):
    r = client.get("/api/cpo/me", headers=cpo_headers)
    assert r.status_code == 200
    assert r.json()["team_name"] == "Engineering"


def test_update_team_name_success(client, seeded_config, cpo_headers):
    r = client.patch("/api/cpo/team-name", json={"team_name": "Pizza Squad"}, headers=cpo_headers)
    assert r.status_code == 200
    assert r.json()["team_name"] == "Pizza Squad"


def test_update_team_name_reflected_in_get_me(client, seeded_config, cpo_headers):
    client.patch("/api/cpo/team-name", json={"team_name": "New Team"}, headers=cpo_headers)
    r = client.get("/api/cpo/me", headers=cpo_headers)
    assert r.json()["team_name"] == "New Team"


def test_update_team_name_rejects_empty(client, seeded_config, cpo_headers):
    r = client.patch("/api/cpo/team-name", json={"team_name": ""}, headers=cpo_headers)
    assert r.status_code == 422


def test_update_team_name_requires_cpo(client, seeded_config, admin_headers):
    r = client.patch("/api/cpo/team-name", json={"team_name": "Pizza Squad"}, headers=admin_headers)
    assert r.status_code == 403


def test_update_team_name_requires_auth(client, seeded_config):
    r = client.patch("/api/cpo/team-name", json={"team_name": "Pizza Squad"})
    assert r.status_code == 401


def test_update_team_name_does_not_affect_existing_sessions(client, seeded_config, seeded_menu, cpo_headers):
    """Session snapshot is preserved — renaming team does not rewrite old session data."""
    import storage
    r = client.post("/api/cpo/sessions", json={
        "session_date": "2099-12-31",
        "start_time": "11:00",
        "end_time": "12:00",
    }, headers=cpo_headers)
    assert r.status_code == 201
    session_id = r.json()["id"]
    original_team_name = r.json()["team_name"]

    client.patch("/api/cpo/team-name", json={"team_name": "Renamed Team"}, headers=cpo_headers)

    cpo_id = seeded_config["cpo_id"]
    session = storage.load_session(cpo_id, session_id)
    assert session.team_name == original_team_name


# ---------------------------------------------------------------------------
# POST /api/cpo/sessions
# ---------------------------------------------------------------------------

SESSION_BODY = {
    "session_date": _FUTURE,
    "start_time": "11:30",
    "end_time": "12:00",
    "grace_period_minutes": 2,
}


def test_create_session_success(client, seeded_config, seeded_menu, cpo_headers):
    r = client.post("/api/cpo/sessions", json=SESSION_BODY, headers=cpo_headers)
    assert r.status_code == 201
    body = r.json()
    assert body["start_time"] == "11:30"
    assert body["end_time"] == "12:00"
    assert body["team_name"] == "Engineering"
    assert "unique_link" in body
    assert "id" in body


def test_create_session_includes_status(client, seeded_config, seeded_menu, cpo_headers):
    r = client.post("/api/cpo/sessions", json=SESSION_BODY, headers=cpo_headers)
    assert r.status_code == 201
    assert r.json()["status"] in ("upcoming", "active", "closed")


def test_create_second_active_session_rejected(client, seeded_config, seeded_menu, cpo_headers):
    # First session: upcoming (start time in the future)
    r1 = client.post("/api/cpo/sessions", json=SESSION_BODY, headers=cpo_headers)
    assert r1.status_code == 201
    # Second session should be rejected
    r2 = client.post("/api/cpo/sessions", json={**SESSION_BODY, "start_time": "13:00", "end_time": "14:00"}, headers=cpo_headers)
    assert r2.status_code == 409


def test_create_session_without_menu_rejected(client, seeded_config, cpo_headers):
    """No menus defined → the session cannot be started."""
    r = client.post("/api/cpo/sessions", json=SESSION_BODY, headers=cpo_headers)
    assert r.status_code == 422
    assert "menu" in r.json()["detail"].lower()


def test_create_session_uses_default_menu_when_omitted(client, seeded_config, seeded_menu, cpo_headers):
    r = client.post("/api/cpo/sessions", json=SESSION_BODY, headers=cpo_headers)
    assert r.status_code == 201
    assert r.json()["menu_id"] == seeded_menu.id


def test_create_session_with_explicit_menu(client, seeded_config, seeded_menu, cpo_headers):
    other = client.post("/api/cpo/menus", json={"name": "Thai"}, headers=cpo_headers).json()
    r = client.post(
        "/api/cpo/sessions",
        json={**SESSION_BODY, "menu_id": other["id"]},
        headers=cpo_headers,
    )
    assert r.status_code == 201
    assert r.json()["menu_id"] == other["id"]


def test_create_session_with_unknown_menu_rejected(client, seeded_config, seeded_menu, cpo_headers):
    r = client.post(
        "/api/cpo/sessions",
        json={**SESSION_BODY, "menu_id": new_id()},
        headers=cpo_headers,
    )
    assert r.status_code == 422


def test_create_session_invalid_time(client, seeded_config, cpo_headers):
    r = client.post(
        "/api/cpo/sessions",
        json={**SESSION_BODY, "start_time": "99:99"},
        headers=cpo_headers,
    )
    assert r.status_code == 422


def test_create_session_end_before_start_rejected(client, seeded_config, seeded_menu, cpo_headers):
    """end_time <= start_time would span midnight, which isn't supported (#3)."""
    r = client.post(
        "/api/cpo/sessions",
        json={**SESSION_BODY, "start_time": "23:00", "end_time": "01:00"},
        headers=cpo_headers,
    )
    assert r.status_code == 422
    assert "midnight" in r.json()["detail"].lower()


def test_create_session_end_equal_start_rejected(client, seeded_config, seeded_menu, cpo_headers):
    r = client.post(
        "/api/cpo/sessions",
        json={**SESSION_BODY, "start_time": "11:30", "end_time": "11:30"},
        headers=cpo_headers,
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/cpo/sessions
# ---------------------------------------------------------------------------

def test_list_sessions_empty(client, seeded_config, cpo_headers):
    r = client.get("/api/cpo/sessions", headers=cpo_headers)
    assert r.status_code == 200
    assert r.json() == []


def test_list_sessions_after_create(client, seeded_config, seeded_menu, cpo_headers):
    client.post("/api/cpo/sessions", json=SESSION_BODY, headers=cpo_headers)
    r = client.get("/api/cpo/sessions", headers=cpo_headers)
    assert r.status_code == 200
    assert len(r.json()) == 1


# ---------------------------------------------------------------------------
# GET /api/cpo/sessions/{id}/summary
# ---------------------------------------------------------------------------

def _seed_session_with_orders(seeded_config, monkeypatch, tmp_path):
    """Helper: save a session file with two orders directly to storage."""
    import config as cfg_module

    team_id = seeded_config["team_id"]
    session = SessionFile(
        id=new_id(),
        team_id=team_id,
        team_name="Engineering",
        session_date=date(2026, 5, 14),
        start_time="11:30",
        end_time="12:00",
        created_at=datetime.now(tz=timezone.utc),
    )
    orders = [
        Order(
            id=new_id(),
            session_id=session.id,
            member_name="Alice",
            pizza_id="p1",
            pizza_name="Margherita",
            pizza_price=12.50,
            total_price=12.50,
            created_at=datetime.now(tz=timezone.utc),
            client_ip="10.0.0.1",
        ),
        Order(
            id=new_id(),
            session_id=session.id,
            member_name="Bob",
            pizza_id="p2",
            pizza_name="Pepperoni",
            pizza_price=13.50,
            total_price=13.50,
            created_at=datetime.now(tz=timezone.utc),
            client_ip="10.0.0.2",
        ),
    ]
    session.orders = orders
    storage.save_session(session)
    return session


def test_summary_distribution(client, seeded_config, cpo_headers, monkeypatch, tmp_path):
    session = _seed_session_with_orders(seeded_config, monkeypatch, tmp_path)
    r = client.get(f"/api/cpo/sessions/{session.id}/summary", headers=cpo_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["total_orders"] == 2
    assert len(body["distribution"]) == 2
    names = [row["member_name"] for row in body["distribution"]]
    assert "Alice" in names and "Bob" in names


def test_summary_distribution_sorted_by_name(client, seeded_config, cpo_headers, monkeypatch, tmp_path):
    session = _seed_session_with_orders(seeded_config, monkeypatch, tmp_path)
    r = client.get(f"/api/cpo/sessions/{session.id}/summary", headers=cpo_headers)
    names = [row["member_name"] for row in r.json()["distribution"]]
    assert names == sorted(names, key=str.lower)


def test_summary_pizzeria_aggregation(client, seeded_config, cpo_headers, monkeypatch, tmp_path):
    session = _seed_session_with_orders(seeded_config, monkeypatch, tmp_path)
    r = client.get(f"/api/cpo/sessions/{session.id}/summary", headers=cpo_headers)
    body = r.json()
    pizzeria = {row["pizza_name"]: row for row in body["pizzeria"]}
    assert pizzeria["Margherita"]["count"] == 1
    assert pizzeria["Pepperoni"]["count"] == 1


def test_summary_total_price(client, seeded_config, cpo_headers, monkeypatch, tmp_path):
    session = _seed_session_with_orders(seeded_config, monkeypatch, tmp_path)
    r = client.get(f"/api/cpo/sessions/{session.id}/summary", headers=cpo_headers)
    assert r.json()["total_price"] == pytest.approx(26.00, abs=1e-6)


def test_summary_not_found(client, seeded_config, cpo_headers):
    r = client.get("/api/cpo/sessions/00000000-0000-0000-0000-000000000000/summary", headers=cpo_headers)
    assert r.status_code == 404


def test_summary_distribution_includes_comment(client, seeded_config, cpo_headers, monkeypatch, tmp_path):
    team_id = seeded_config["team_id"]
    session = SessionFile(
        id=new_id(),
        team_id=team_id,
        team_name="Engineering",
        session_date=date(2026, 5, 14),
        start_time="11:30",
        end_time="12:00",
        created_at=datetime.now(tz=timezone.utc),
    )
    session.orders = [
        Order(
            id=new_id(), session_id=session.id, member_name="Alice",
            pizza_id="p1", pizza_name="Margherita", pizza_price=12.50,
            total_price=12.50, created_at=datetime.now(tz=timezone.utc),
            client_ip="10.0.0.1", comment="no olives",
        ),
        Order(
            id=new_id(), session_id=session.id, member_name="Bob",
            pizza_id="p1", pizza_name="Margherita", pizza_price=12.50,
            total_price=12.50, created_at=datetime.now(tz=timezone.utc),
            client_ip="10.0.0.2", comment=None,
        ),
    ]
    storage.save_session(session)

    r = client.get(f"/api/cpo/sessions/{session.id}/summary", headers=cpo_headers)
    assert r.status_code == 200
    dist = {row["member_name"]: row for row in r.json()["distribution"]}
    assert dist["Alice"]["comment"] == "no olives"
    assert dist["Bob"]["comment"] is None


def test_summary_pizzeria_comment_aggregation(client, seeded_config, cpo_headers, monkeypatch, tmp_path):
    team_id = seeded_config["team_id"]
    session = SessionFile(
        id=new_id(),
        team_id=team_id,
        team_name="Engineering",
        session_date=date(2026, 5, 14),
        start_time="11:30",
        end_time="12:00",
        created_at=datetime.now(tz=timezone.utc),
    )
    session.orders = [
        Order(
            id=new_id(), session_id=session.id, member_name="Alice",
            pizza_id="p1", pizza_name="Margherita", pizza_price=12.50,
            total_price=12.50, created_at=datetime.now(tz=timezone.utc),
            client_ip="10.0.0.1", comment="no olives",
        ),
        Order(
            id=new_id(), session_id=session.id, member_name="Bob",
            pizza_id="p1", pizza_name="Margherita", pizza_price=12.50,
            total_price=12.50, created_at=datetime.now(tz=timezone.utc),
            client_ip="10.0.0.2", comment="no olives",
        ),
        Order(
            id=new_id(), session_id=session.id, member_name="Carol",
            pizza_id="p1", pizza_name="Margherita", pizza_price=12.50,
            total_price=12.50, created_at=datetime.now(tz=timezone.utc),
            client_ip="10.0.0.3", comment="extra cheese",
        ),
        Order(
            id=new_id(), session_id=session.id, member_name="Dan",
            pizza_id="p1", pizza_name="Margherita", pizza_price=12.50,
            total_price=12.50, created_at=datetime.now(tz=timezone.utc),
            client_ip="10.0.0.4", comment=None,
        ),
    ]
    storage.save_session(session)

    r = client.get(f"/api/cpo/sessions/{session.id}/summary", headers=cpo_headers)
    assert r.status_code == 200
    pizzeria = {row["pizza_name"]: row for row in r.json()["pizzeria"]}
    comments = {c["text"]: c["count"] for c in pizzeria["Margherita"]["comments"]}
    assert comments["no olives"] == 2
    assert comments["extra cheese"] == 1
    assert len(comments) == 2  # null orders not counted


# ---------------------------------------------------------------------------
# Menus CRUD
# ---------------------------------------------------------------------------

def _create_menu(client, cpo_headers, name="Default", **extra) -> dict:
    r = client.post("/api/cpo/menus", json={"name": name, **extra}, headers=cpo_headers)
    assert r.status_code == 201
    return r.json()


def test_menus_start_empty(client, seeded_config, cpo_headers):
    r = client.get("/api/cpo/menus", headers=cpo_headers)
    assert r.status_code == 200
    assert r.json() == []


def test_create_menu(client, seeded_config, cpo_headers):
    body = _create_menu(client, cpo_headers, name="Pizzas")
    assert body["name"] == "Pizzas"
    assert body["is_default"] is True   # first menu becomes the default
    assert body["pizzeria_url"] is None
    assert body["pizza_count"] == 0


def test_second_menu_not_default(client, seeded_config, cpo_headers):
    _create_menu(client, cpo_headers, name="Pizzas")
    second = _create_menu(client, cpo_headers, name="Thai")
    assert second["is_default"] is False


def test_create_menu_duplicate_name(client, seeded_config, cpo_headers):
    _create_menu(client, cpo_headers, name="Pizzas")
    r = client.post("/api/cpo/menus", json={"name": "pizzas"}, headers=cpo_headers)
    assert r.status_code == 409


def test_create_menu_with_url(client, seeded_config, cpo_headers):
    body = _create_menu(client, cpo_headers, name="Pizzas", pizzeria_url="https://pizza.example.com")
    assert body["pizzeria_url"] == "https://pizza.example.com"


def test_create_menu_blank_name_rejected(client, seeded_config, cpo_headers):
    r = client.post("/api/cpo/menus", json={"name": "   "}, headers=cpo_headers)
    assert r.status_code == 422


def test_rename_menu(client, seeded_config, cpo_headers):
    menu = _create_menu(client, cpo_headers, name="Pizzas")
    r = client.patch(f"/api/cpo/menus/{menu['id']}", json={"name": "Italian"}, headers=cpo_headers)
    assert r.status_code == 200
    assert r.json()["name"] == "Italian"


def test_rename_menu_duplicate_name(client, seeded_config, cpo_headers):
    _create_menu(client, cpo_headers, name="Pizzas")
    other = _create_menu(client, cpo_headers, name="Thai")
    r = client.patch(f"/api/cpo/menus/{other['id']}", json={"name": "Pizzas"}, headers=cpo_headers)
    assert r.status_code == 409


def test_rename_menu_same_name_allowed(client, seeded_config, cpo_headers):
    menu = _create_menu(client, cpo_headers, name="Pizzas")
    r = client.patch(f"/api/cpo/menus/{menu['id']}", json={"name": "Pizzas"}, headers=cpo_headers)
    assert r.status_code == 200


def test_update_menu_not_found(client, seeded_config, cpo_headers):
    r = client.patch(f"/api/cpo/menus/{new_id()}", json={"name": "X"}, headers=cpo_headers)
    assert r.status_code == 404


def test_update_menu_url_omitted_keeps_value(client, seeded_config, cpo_headers):
    menu = _create_menu(client, cpo_headers, name="Pizzas", pizzeria_url="https://keep.example.com")
    r = client.patch(f"/api/cpo/menus/{menu['id']}", json={"name": "Renamed"}, headers=cpo_headers)
    assert r.json()["pizzeria_url"] == "https://keep.example.com"


def test_update_menu_url_null_clears(client, seeded_config, cpo_headers):
    menu = _create_menu(client, cpo_headers, name="Pizzas", pizzeria_url="https://old.example.com")
    r = client.patch(f"/api/cpo/menus/{menu['id']}", json={"pizzeria_url": None}, headers=cpo_headers)
    assert r.status_code == 200
    assert r.json()["pizzeria_url"] is None


def test_set_default_menu(client, seeded_config, cpo_headers):
    _create_menu(client, cpo_headers, name="Pizzas")
    other = _create_menu(client, cpo_headers, name="Thai")
    r = client.post(f"/api/cpo/menus/{other['id']}/default", headers=cpo_headers)
    assert r.status_code == 204
    menus = {m["name"]: m for m in client.get("/api/cpo/menus", headers=cpo_headers).json()}
    assert menus["Thai"]["is_default"] is True
    assert menus["Pizzas"]["is_default"] is False


def test_set_default_menu_idempotent(client, seeded_config, cpo_headers):
    menu = _create_menu(client, cpo_headers, name="Pizzas")
    assert client.post(f"/api/cpo/menus/{menu['id']}/default", headers=cpo_headers).status_code == 204
    assert client.post(f"/api/cpo/menus/{menu['id']}/default", headers=cpo_headers).status_code == 204
    assert client.get("/api/cpo/menus", headers=cpo_headers).json()[0]["is_default"] is True


def test_set_default_menu_not_found(client, seeded_config, cpo_headers):
    r = client.post(f"/api/cpo/menus/{new_id()}/default", headers=cpo_headers)
    assert r.status_code == 404


def test_delete_menu(client, seeded_config, cpo_headers):
    _create_menu(client, cpo_headers, name="Pizzas")
    other = _create_menu(client, cpo_headers, name="Thai")
    r = client.delete(f"/api/cpo/menus/{other['id']}", headers=cpo_headers)
    assert r.status_code == 204
    names = [m["name"] for m in client.get("/api/cpo/menus", headers=cpo_headers).json()]
    assert names == ["Pizzas"]


def test_delete_menu_not_found(client, seeded_config, cpo_headers):
    r = client.delete(f"/api/cpo/menus/{new_id()}", headers=cpo_headers)
    assert r.status_code == 404


def test_delete_default_menu_promotes_oldest(client, seeded_config, cpo_headers):
    first = _create_menu(client, cpo_headers, name="Pizzas")
    _create_menu(client, cpo_headers, name="Thai")
    _create_menu(client, cpo_headers, name="Burgers")
    r = client.delete(f"/api/cpo/menus/{first['id']}", headers=cpo_headers)
    assert r.status_code == 204
    menus = client.get("/api/cpo/menus", headers=cpo_headers).json()
    assert [m["name"] for m in menus] == ["Thai", "Burgers"]
    assert [m["is_default"] for m in menus] == [True, False]


def test_delete_last_menu_blocks_new_sessions(client, seeded_config, cpo_headers):
    menu = _create_menu(client, cpo_headers, name="Pizzas")
    assert client.delete(f"/api/cpo/menus/{menu['id']}", headers=cpo_headers).status_code == 204
    r = client.post("/api/cpo/sessions", json=SESSION_BODY, headers=cpo_headers)
    assert r.status_code == 422


def test_delete_menu_in_use_by_upcoming_session_rejected(client, seeded_config, seeded_menu, cpo_headers):
    r1 = client.post("/api/cpo/sessions", json=SESSION_BODY, headers=cpo_headers)
    assert r1.status_code == 201
    r = client.delete(f"/api/cpo/menus/{seeded_menu.id}", headers=cpo_headers)
    assert r.status_code == 409
    assert "session" in r.json()["detail"].lower()


def test_delete_menu_allowed_after_session_closed(client, seeded_config, seeded_menu, cpo_headers):
    r1 = client.post("/api/cpo/sessions", json=SESSION_BODY, headers=cpo_headers)
    session_id = r1.json()["id"]
    client.post(f"/api/cpo/sessions/{session_id}/close", headers=cpo_headers)
    r = client.delete(f"/api/cpo/menus/{seeded_menu.id}", headers=cpo_headers)
    assert r.status_code == 204


def test_menus_scoped_to_cpo(client, seeded_config, admin_headers, cpo_headers):
    """Another CPO's menu is invisible: 404 on direct access.

    admin_service.create_cpo() always mints a brand-new team (different
    team_id) for "mary", so this proves cross-TEAM isolation still holds —
    not merely cross-login isolation."""
    create = client.post(
        "/api/admin/cpos",
        json={
            "username": "mary",
            "email": "mary@example.com",
            "team_name": "Design",
            "initial_password": "DesignPass8899",  # NOSONAR
        },
        headers=admin_headers,
    )
    assert create.status_code == 201
    assert create.json()["team_id"] != seeded_config["team_id"]
    mary_login_id = create.json()["members"][0]["id"]
    from security import create_token
    other_headers = {"Authorization": f"Bearer {create_token(mary_login_id, 'cpo')}"}
    other_menu = _create_menu(client, other_headers, name="Mary's menu")

    r = client.patch(f"/api/cpo/menus/{other_menu['id']}", json={"name": "Hijack"}, headers=cpo_headers)
    assert r.status_code == 404
    assert client.get("/api/cpo/menus", headers=cpo_headers).json() == []


def test_menus_visible_to_same_team_peer(client, seeded_config, cpo_headers, second_team_member_headers):
    """A second CPO login on the SAME team can see and edit the first
    login's menus — same-team sharing works (the counterpart to
    test_menus_scoped_to_cpo's cross-team isolation)."""
    menu = _create_menu(client, cpo_headers, name="Shared Menu")

    listed = client.get("/api/cpo/menus", headers=second_team_member_headers).json()
    assert [m["id"] for m in listed] == [menu["id"]]

    r = client.patch(
        f"/api/cpo/menus/{menu['id']}", json={"name": "Renamed by peer"},
        headers=second_team_member_headers,
    )
    assert r.status_code == 200
    assert r.json()["name"] == "Renamed by peer"


def test_sessions_visible_to_same_team_peer(
    client, seeded_config, seeded_menu, cpo_headers, second_team_member_headers
):
    """A second CPO login on the SAME team sees sessions the first created."""
    created = client.post("/api/cpo/sessions", json=SESSION_BODY, headers=cpo_headers)
    assert created.status_code == 201

    r = client.get("/api/cpo/sessions", headers=second_team_member_headers)
    assert r.status_code == 200
    assert [s["id"] for s in r.json()] == [created.json()["id"]]


# ---------------------------------------------------------------------------
# Pizza CRUD (menu-scoped)
# ---------------------------------------------------------------------------

def _menu_id(client, cpo_headers) -> str:
    return _create_menu(client, cpo_headers)["id"]


def test_menu_starts_empty(client, seeded_config, cpo_headers):
    menu_id = _menu_id(client, cpo_headers)
    r = client.get(f"/api/cpo/menus/{menu_id}/pizzas", headers=cpo_headers)
    assert r.status_code == 200
    assert r.json() == []


def test_add_pizza(client, seeded_config, cpo_headers):
    menu_id = _menu_id(client, cpo_headers)
    r = client.post(f"/api/cpo/menus/{menu_id}/pizzas", json={"name": "Margherita", "price": 12.50}, headers=cpo_headers)
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Margherita"
    assert body["price"] == pytest.approx(12.50, abs=1e-6)
    assert "id" in body


def test_add_pizza_duplicate_name(client, seeded_config, cpo_headers):
    menu_id = _menu_id(client, cpo_headers)
    client.post(f"/api/cpo/menus/{menu_id}/pizzas", json={"name": "Margherita", "price": 12.50}, headers=cpo_headers)
    r = client.post(f"/api/cpo/menus/{menu_id}/pizzas", json={"name": "Margherita", "price": 9.00}, headers=cpo_headers)
    assert r.status_code == 409


def test_add_pizza_case_insensitive_duplicate(client, seeded_config, cpo_headers):
    menu_id = _menu_id(client, cpo_headers)
    client.post(f"/api/cpo/menus/{menu_id}/pizzas", json={"name": "Margherita", "price": 12.50}, headers=cpo_headers)
    r = client.post(f"/api/cpo/menus/{menu_id}/pizzas", json={"name": "margherita", "price": 9.00}, headers=cpo_headers)
    assert r.status_code == 409


def test_same_pizza_name_allowed_across_menus(client, seeded_config, cpo_headers):
    first = _create_menu(client, cpo_headers, name="Pizzas")
    second = _create_menu(client, cpo_headers, name="Thai")
    client.post(f"/api/cpo/menus/{first['id']}/pizzas", json={"name": "Special", "price": 12.50}, headers=cpo_headers)
    r = client.post(f"/api/cpo/menus/{second['id']}/pizzas", json={"name": "Special", "price": 9.00}, headers=cpo_headers)
    assert r.status_code == 201


def test_add_pizza_invalid_price(client, seeded_config, cpo_headers):
    menu_id = _menu_id(client, cpo_headers)
    r = client.post(f"/api/cpo/menus/{menu_id}/pizzas", json={"name": "Free Pizza", "price": 0.0}, headers=cpo_headers)
    assert r.status_code == 422


def test_add_pizza_unknown_menu(client, seeded_config, cpo_headers):
    r = client.post(f"/api/cpo/menus/{new_id()}/pizzas", json={"name": "X", "price": 10.0}, headers=cpo_headers)
    assert r.status_code == 404


def test_update_pizza(client, seeded_config, cpo_headers):
    menu_id = _menu_id(client, cpo_headers)
    create = client.post(f"/api/cpo/menus/{menu_id}/pizzas", json={"name": "Margherita", "price": 12.50}, headers=cpo_headers)
    pizza_id = create.json()["id"]
    r = client.put(f"/api/cpo/menus/{menu_id}/pizzas/{pizza_id}", json={"name": "Margherita Extra", "price": 14.00}, headers=cpo_headers)
    assert r.status_code == 200
    assert r.json()["name"] == "Margherita Extra"
    assert r.json()["price"] == pytest.approx(14.00, abs=1e-6)


def test_update_pizza_duplicate_name(client, seeded_config, cpo_headers):
    menu_id = _menu_id(client, cpo_headers)
    client.post(f"/api/cpo/menus/{menu_id}/pizzas", json={"name": "Margherita", "price": 12.50}, headers=cpo_headers)
    r2 = client.post(f"/api/cpo/menus/{menu_id}/pizzas", json={"name": "Pepperoni", "price": 13.00}, headers=cpo_headers)
    pizza_id = r2.json()["id"]
    r = client.put(f"/api/cpo/menus/{menu_id}/pizzas/{pizza_id}", json={"name": "Margherita", "price": 13.00}, headers=cpo_headers)
    assert r.status_code == 409


def test_update_pizza_same_name_allowed(client, seeded_config, cpo_headers):
    """Updating a pizza to keep the same name should succeed."""
    menu_id = _menu_id(client, cpo_headers)
    create = client.post(f"/api/cpo/menus/{menu_id}/pizzas", json={"name": "Margherita", "price": 12.50}, headers=cpo_headers)
    pizza_id = create.json()["id"]
    r = client.put(f"/api/cpo/menus/{menu_id}/pizzas/{pizza_id}", json={"name": "Margherita", "price": 15.00}, headers=cpo_headers)
    assert r.status_code == 200


def test_update_pizza_not_found(client, seeded_config, cpo_headers):
    menu_id = _menu_id(client, cpo_headers)
    r = client.put(f"/api/cpo/menus/{menu_id}/pizzas/nonexistent", json={"name": "X", "price": 10.0}, headers=cpo_headers)
    assert r.status_code == 404


def test_delete_pizza(client, seeded_config, cpo_headers):
    menu_id = _menu_id(client, cpo_headers)
    create = client.post(f"/api/cpo/menus/{menu_id}/pizzas", json={"name": "Margherita", "price": 12.50}, headers=cpo_headers)
    pizza_id = create.json()["id"]
    r = client.delete(f"/api/cpo/menus/{menu_id}/pizzas/{pizza_id}", headers=cpo_headers)
    assert r.status_code == 204
    # verify gone
    menu = client.get(f"/api/cpo/menus/{menu_id}/pizzas", headers=cpo_headers)
    assert menu.json() == []


def test_delete_pizza_not_found(client, seeded_config, cpo_headers):
    menu_id = _menu_id(client, cpo_headers)
    r = client.delete(f"/api/cpo/menus/{menu_id}/pizzas/nonexistent", headers=cpo_headers)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Menu export / import
# ---------------------------------------------------------------------------

def test_export_menu_empty(client, seeded_config, cpo_headers):
    menu_id = _menu_id(client, cpo_headers)
    r = client.get(f"/api/cpo/menus/{menu_id}/export", headers=cpo_headers)
    assert r.status_code == 200
    assert "attachment" in r.headers.get("content-disposition", "")
    body = r.json()
    assert body["dishes"] == []
    assert body["url"] is None
    assert "cpo_id" not in body


def test_export_menu_with_data(client, seeded_config, cpo_headers):
    menu_id = _menu_id(client, cpo_headers)
    client.post(f"/api/cpo/menus/{menu_id}/pizzas", json={"name": "Margherita", "price": 12.50}, headers=cpo_headers)
    client.post(f"/api/cpo/menus/{menu_id}/pizzas", json={"name": "Pepperoni",  "price": 13.50}, headers=cpo_headers)
    client.patch(f"/api/cpo/menus/{menu_id}", json={"pizzeria_url": "https://pizza.example.com"}, headers=cpo_headers)

    r = client.get(f"/api/cpo/menus/{menu_id}/export", headers=cpo_headers)
    assert r.status_code == 200
    body = r.json()
    assert len(body["dishes"]) == 2
    names = {p["name"] for p in body["dishes"]}
    assert names == {"Margherita", "Pepperoni"}
    assert body["url"] == "https://pizza.example.com"
    # no internal fields
    for p in body["dishes"]:
        assert "id" not in p
        assert "cpo_id" not in p


def test_import_replaces_menu(client, seeded_config, cpo_headers):
    menu_id = _menu_id(client, cpo_headers)
    client.post(f"/api/cpo/menus/{menu_id}/pizzas", json={"name": "Old Pizza", "price": 10.00}, headers=cpo_headers)

    r = client.post(
        f"/api/cpo/menus/{menu_id}/import",
        json={"dishes": [{"name": "New Pizza", "price": 15.00}]},
        headers=cpo_headers,
    )
    assert r.status_code == 204

    menu = client.get(f"/api/cpo/menus/{menu_id}/pizzas", headers=cpo_headers).json()
    assert len(menu) == 1
    assert menu[0]["name"] == "New Pizza"
    assert menu[0]["price"] == pytest.approx(15.00, abs=1e-6)
    assert "id" in menu[0]   # new UUID assigned


def test_import_replaces_with_empty(client, seeded_config, cpo_headers):
    menu_id = _menu_id(client, cpo_headers)
    client.post(f"/api/cpo/menus/{menu_id}/pizzas", json={"name": "Pizza", "price": 10.00}, headers=cpo_headers)

    r = client.post(f"/api/cpo/menus/{menu_id}/import", json={"dishes": []}, headers=cpo_headers)
    assert r.status_code == 204
    assert client.get(f"/api/cpo/menus/{menu_id}/pizzas", headers=cpo_headers).json() == []


def test_import_only_touches_target_menu(client, seeded_config, cpo_headers):
    first = _create_menu(client, cpo_headers, name="Pizzas")
    second = _create_menu(client, cpo_headers, name="Thai")
    client.post(f"/api/cpo/menus/{first['id']}/pizzas", json={"name": "Margherita", "price": 12.50}, headers=cpo_headers)

    r = client.post(
        f"/api/cpo/menus/{second['id']}/import",
        json={"dishes": [{"name": "Pad Thai", "price": 16.00}]},
        headers=cpo_headers,
    )
    assert r.status_code == 204
    first_pizzas = client.get(f"/api/cpo/menus/{first['id']}/pizzas", headers=cpo_headers).json()
    assert [p["name"] for p in first_pizzas] == ["Margherita"]
    second_pizzas = client.get(f"/api/cpo/menus/{second['id']}/pizzas", headers=cpo_headers).json()
    assert [p["name"] for p in second_pizzas] == ["Pad Thai"]


def _menu_url(client, cpo_headers, menu_id) -> str | None:
    menus = client.get("/api/cpo/menus", headers=cpo_headers).json()
    return next(m["pizzeria_url"] for m in menus if m["id"] == menu_id)


def test_import_sets_pizzeria_url(client, seeded_config, cpo_headers):
    menu_id = _menu_id(client, cpo_headers)
    r = client.post(
        f"/api/cpo/menus/{menu_id}/import",
        json={"dishes": [], "url": "https://new-pizzeria.example.com"},
        headers=cpo_headers,
    )
    assert r.status_code == 204
    assert _menu_url(client, cpo_headers, menu_id) == "https://new-pizzeria.example.com"


def test_import_clears_pizzeria_url(client, seeded_config, cpo_headers):
    menu_id = _menu_id(client, cpo_headers)
    client.patch(f"/api/cpo/menus/{menu_id}", json={"pizzeria_url": "https://old.example.com"}, headers=cpo_headers)

    r = client.post(f"/api/cpo/menus/{menu_id}/import", json={"dishes": [], "url": None}, headers=cpo_headers)
    assert r.status_code == 204
    assert _menu_url(client, cpo_headers, menu_id) is None


def test_import_duplicate_names_in_file(client, seeded_config, cpo_headers):
    menu_id = _menu_id(client, cpo_headers)
    r = client.post(
        f"/api/cpo/menus/{menu_id}/import",
        json={"dishes": [{"name": "Pizza", "price": 10.00}, {"name": "pizza", "price": 12.00}]},
        headers=cpo_headers,
    )
    assert r.status_code == 422


def test_import_invalid_price(client, seeded_config, cpo_headers):
    menu_id = _menu_id(client, cpo_headers)
    r = client.post(
        f"/api/cpo/menus/{menu_id}/import",
        json={"dishes": [{"name": "Free Pizza", "price": 0.0}]},
        headers=cpo_headers,
    )
    assert r.status_code == 422


def test_import_invalid_url(client, seeded_config, cpo_headers):
    menu_id = _menu_id(client, cpo_headers)
    r = client.post(
        f"/api/cpo/menus/{menu_id}/import",
        json={"dishes": [], "url": "ftp://bad.example.com"},
        headers=cpo_headers,
    )
    assert r.status_code == 422


def test_export_import_roundtrip(client, seeded_config, cpo_headers):
    menu_id = _menu_id(client, cpo_headers)
    client.post(f"/api/cpo/menus/{menu_id}/pizzas", json={"name": "Margherita", "price": 12.50}, headers=cpo_headers)
    client.post(f"/api/cpo/menus/{menu_id}/pizzas", json={"name": "Hawaii",     "price": 14.00}, headers=cpo_headers)
    client.patch(f"/api/cpo/menus/{menu_id}", json={"pizzeria_url": "https://roundtrip.example.com"}, headers=cpo_headers)

    exported = client.get(f"/api/cpo/menus/{menu_id}/export", headers=cpo_headers).json()
    client.post(f"/api/cpo/menus/{menu_id}/import", json=exported, headers=cpo_headers)

    menu = client.get(f"/api/cpo/menus/{menu_id}/pizzas", headers=cpo_headers).json()
    assert {p["name"] for p in menu} == {"Margherita", "Hawaii"}
    by_name = {p["name"]: p["price"] for p in menu}
    assert by_name["Margherita"] == pytest.approx(12.50, abs=1e-6)
    assert by_name["Hawaii"]     == pytest.approx(14.00, abs=1e-6)
    assert _menu_url(client, cpo_headers, menu_id) == "https://roundtrip.example.com"


# ---------------------------------------------------------------------------
# Order deletion (CPO action)
# ---------------------------------------------------------------------------

def test_delete_order(client, seeded_config, cpo_headers, monkeypatch, tmp_path):
    session = _seed_session_with_orders(seeded_config, monkeypatch, tmp_path)
    order_id = session.orders[0].id
    r = client.delete(f"/api/cpo/orders/{order_id}", headers=cpo_headers)
    assert r.status_code == 204
    # verify removed from summary
    summary = client.get(f"/api/cpo/sessions/{session.id}/summary", headers=cpo_headers)
    assert summary.json()["total_orders"] == 1


def test_delete_order_not_found(client, seeded_config, cpo_headers):
    r = client.delete("/api/cpo/orders/nonexistent", headers=cpo_headers)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /api/cpo/orders/{order_id}/received
# ---------------------------------------------------------------------------

def test_set_received_true(client, seeded_config, cpo_headers, monkeypatch, tmp_path):
    session = _seed_session_with_orders(seeded_config, monkeypatch, tmp_path)
    order_id = session.orders[0].id

    r = client.patch(f"/api/cpo/orders/{order_id}/received", json={"received": True}, headers=cpo_headers)
    assert r.status_code == 204

    summary = client.get(f"/api/cpo/sessions/{session.id}/summary", headers=cpo_headers).json()
    dist = {row["order_id"]: row for row in summary["distribution"]}
    assert dist[order_id]["received"] is True


def test_set_received_false(client, seeded_config, cpo_headers, monkeypatch, tmp_path):
    session = _seed_session_with_orders(seeded_config, monkeypatch, tmp_path)
    order_id = session.orders[0].id

    client.patch(f"/api/cpo/orders/{order_id}/received", json={"received": True}, headers=cpo_headers)
    r = client.patch(f"/api/cpo/orders/{order_id}/received", json={"received": False}, headers=cpo_headers)
    assert r.status_code == 204

    summary = client.get(f"/api/cpo/sessions/{session.id}/summary", headers=cpo_headers).json()
    dist = {row["order_id"]: row for row in summary["distribution"]}
    assert dist[order_id]["received"] is False


def test_set_received_not_found(client, seeded_config, cpo_headers):
    r = client.patch("/api/cpo/orders/nonexistent/received", json={"received": True}, headers=cpo_headers)
    assert r.status_code == 404


def test_set_received_requires_cpo(client, seeded_config, admin_headers, monkeypatch, tmp_path):
    session = _seed_session_with_orders(seeded_config, monkeypatch, tmp_path)
    order_id = session.orders[0].id
    r = client.patch(f"/api/cpo/orders/{order_id}/received", json={"received": True}, headers=admin_headers)
    assert r.status_code == 403


def test_summary_distribution_received_defaults_false(client, seeded_config, cpo_headers, monkeypatch, tmp_path):
    session = _seed_session_with_orders(seeded_config, monkeypatch, tmp_path)
    summary = client.get(f"/api/cpo/sessions/{session.id}/summary", headers=cpo_headers).json()
    for row in summary["distribution"]:
        assert row["received"] is False


def test_received_persists_across_summary_fetch(client, seeded_config, cpo_headers, monkeypatch, tmp_path):
    session = _seed_session_with_orders(seeded_config, monkeypatch, tmp_path)
    order_id = session.orders[1].id

    client.patch(f"/api/cpo/orders/{order_id}/received", json={"received": True}, headers=cpo_headers)

    summary = client.get(f"/api/cpo/sessions/{session.id}/summary", headers=cpo_headers).json()
    dist = {row["order_id"]: row for row in summary["distribution"]}
    assert dist[order_id]["received"] is True
    other_id = session.orders[0].id
    assert dist[other_id]["received"] is False


# ---------------------------------------------------------------------------
# Force-close session
# ---------------------------------------------------------------------------

def _active_session(seeded_config) -> SessionFile:
    now = _utcnow()
    session = SessionFile(
        id=new_id(),
        team_id=seeded_config["team_id"],
        team_name="Engineering",
        session_date=now.date(),
        start_time=(now - timedelta(hours=1)).strftime("%H:%M"),
        end_time=(now + timedelta(hours=1)).strftime("%H:%M"),
        created_at=datetime.now(tz=timezone.utc),
    )
    storage.save_session(session)
    return session


def test_close_session_success(client, seeded_config, cpo_headers):
    session = _active_session(seeded_config)
    r = client.post(f"/api/cpo/sessions/{session.id}/close", headers=cpo_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "closed"


def test_close_session_reflected_in_summary(client, seeded_config, cpo_headers):
    session = _active_session(seeded_config)
    client.post(f"/api/cpo/sessions/{session.id}/close", headers=cpo_headers)
    r = client.get(f"/api/cpo/sessions/{session.id}/summary", headers=cpo_headers)
    assert r.json()["status"] == "closed"


def test_close_session_allows_new_session(client, seeded_config, seeded_menu, cpo_headers):
    """After force-closing, the CPO can open a fresh session."""
    session = _active_session(seeded_config)
    client.post(f"/api/cpo/sessions/{session.id}/close", headers=cpo_headers)

    now = _utcnow()
    r = client.post("/api/cpo/sessions", json={
        "session_date": now.date().isoformat(),
        "start_time": now.strftime("%H:%M"),
        "end_time": (now + timedelta(hours=2)).strftime("%H:%M"),
    }, headers=cpo_headers)
    assert r.status_code == 201


def test_close_already_closed_session(client, seeded_config, cpo_headers):
    session = _active_session(seeded_config)
    client.post(f"/api/cpo/sessions/{session.id}/close", headers=cpo_headers)
    # Second close attempt → conflict
    r = client.post(f"/api/cpo/sessions/{session.id}/close", headers=cpo_headers)
    assert r.status_code == 409


def test_close_session_not_found(client, seeded_config, cpo_headers):
    r = client.post("/api/cpo/sessions/00000000-0000-0000-0000-000000000000/close", headers=cpo_headers)
    assert r.status_code == 404


def test_close_session_requires_cpo(client, seeded_config, admin_headers):
    session = _active_session(seeded_config)
    r = client.post(f"/api/cpo/sessions/{session.id}/close", headers=admin_headers)
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Session UUID path validation (MED-4)
# ---------------------------------------------------------------------------

def test_session_id_non_uuid_returns_422(client, seeded_config, cpo_headers):
    r = client.get("/api/cpo/sessions/not-a-uuid/summary", headers=cpo_headers)
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Pizzeria URL validation (HIGH-4)
# ---------------------------------------------------------------------------

def test_pizzeria_url_rejects_javascript_scheme(client, seeded_config, cpo_headers):
    menu_id = _menu_id(client, cpo_headers)
    r = client.patch(f"/api/cpo/menus/{menu_id}", json={"pizzeria_url": "javascript:alert(1)"}, headers=cpo_headers)
    assert r.status_code == 422


def test_pizzeria_url_rejects_ftp_scheme(client, seeded_config, cpo_headers):
    menu_id = _menu_id(client, cpo_headers)
    r = client.patch(f"/api/cpo/menus/{menu_id}", json={"pizzeria_url": "ftp://example.com/menu"}, headers=cpo_headers)
    assert r.status_code == 422


def test_pizzeria_url_accepts_https(client, seeded_config, cpo_headers):
    menu_id = _menu_id(client, cpo_headers)
    r = client.patch(f"/api/cpo/menus/{menu_id}", json={"pizzeria_url": "https://example.com/menu"}, headers=cpo_headers)
    assert r.status_code == 200
    assert r.json()["pizzeria_url"] == "https://example.com/menu"


def test_pizzeria_url_accepts_null(client, seeded_config, cpo_headers):
    menu_id = _menu_id(client, cpo_headers)
    r = client.patch(f"/api/cpo/menus/{menu_id}", json={"pizzeria_url": None}, headers=cpo_headers)
    assert r.status_code == 200
    assert r.json()["pizzeria_url"] is None
