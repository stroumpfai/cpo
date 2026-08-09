"""Every user-facing failure carries a stable, translatable code.

Two guards live here:

  * each failure path returns a `code` from `error_codes.CODES` next to the
    unchanged English `detail` — the wording itself is pinned by the other test
    modules, which still read `r.json()["detail"]`;
  * every registered code has a non-empty `errors.<code>` string in the
    front-end's English locale file. Without it the React client silently falls
    back to the English `detail` in all four languages, which is exactly the
    drift this suite exists to catch.
"""
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

import storage
from error_codes import CODES, AppError
from models import SessionFile
from services import admin_service, order_service, team_service
from utils import new_id

_EN_LOCALE = (
    Path(__file__).resolve().parents[2] / "frontend" / "src" / "i18n" / "locales" / "en.json"
)

_FUTURE = date.today() + timedelta(days=1)
_UNKNOWN_UUID = "00000000-0000-0000-0000-000000000000"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _assert_error(response, status_code: int, code: str, detail: str | None = None) -> dict:
    """Assert the §1.4 envelope: English detail + registered code + params."""
    assert response.status_code == status_code, response.text
    body = response.json()
    assert body["code"] == code, body
    assert body["code"] in CODES
    assert isinstance(body["params"], dict)
    if detail is not None:
        assert body["detail"] == detail
    return body


def _link(seeded_config) -> str:
    return seeded_config["team"].unique_link


def _active_session(seeded_config, menu_id: str) -> SessionFile:
    session = SessionFile(
        id=new_id(),
        team_id=seeded_config["team_id"],
        team_name="Engineering",
        session_date=date.today(),
        start_time="00:00",
        end_time="23:59",
        grace_period_minutes=2,
        created_at=datetime.now(tz=timezone.utc),
        menu_id=menu_id,
    )
    storage.save_session(session)
    return session


def _email_mode(seeded_config) -> None:
    cfg = storage.load_config()
    next(t for t in cfg.teams if t.id == seeded_config["team_id"]).member_identifier = "email"
    storage.save_config(cfg)


def _submit(client, seeded_config, member_name: str, pizza_id: str):
    order_service.clear_rate_limit()
    return client.post(
        f"/api/orders/{_link(seeded_config)}/submit",
        json={"items": [{"member_name": member_name, "pizza_id": pizza_id}]},
    )


def _open_session(client, cpo_headers, **overrides):
    body = {
        "session_date": _FUTURE.isoformat(),
        "start_time": "11:00",
        "end_time": "12:00",
        "grace_period_minutes": 2,
    }
    body.update(overrides)
    return client.post("/api/cpo/sessions", json=body, headers=cpo_headers)


# ---------------------------------------------------------------------------
# Envelope shape
# ---------------------------------------------------------------------------

def test_envelope_carries_detail_code_and_params(client, seeded_config):
    r = client.post("/api/auth/login", json={"username": "john", "password": "nope"})
    assert r.status_code == 401
    assert r.json() == {
        "detail": "Invalid credentials",
        "code": "invalid_credentials",
        "params": {},
    }


def test_params_carry_the_interpolated_values(client, seeded_config, seeded_menu):
    _active_session(seeded_config, seeded_menu.id)
    r = _submit(client, seeded_config, "A" * 101, seeded_menu.pizzas[0].id)
    body = _assert_error(r, 400, "name_too_long", "Name must be 100 characters or fewer.")
    assert body["params"] == {"max": 100}


def test_plain_http_exception_keeps_the_default_shape(client, seeded_config):
    """security.py's auth guards are not AppErrors — they stay {"detail": …}."""
    r = client.get("/api/cpo/me")
    assert r.status_code == 401
    assert r.json() == {"detail": "Not authenticated"}


def test_request_validation_error_keeps_the_default_shape(client, seeded_config, cpo_headers):
    r = client.post("/api/cpo/menus", json={}, headers=cpo_headers)
    assert r.status_code == 422
    assert "code" not in r.json()


def test_rate_limit_headers_survive_the_handler(client, seeded_config, seeded_menu):
    _active_session(seeded_config, seeded_menu.id)
    pizza_id = seeded_menu.pizzas[0].id
    assert _submit(client, seeded_config, "Alice", pizza_id).status_code == 200
    r = client.post(
        f"/api/orders/{_link(seeded_config)}/submit",
        json={"items": [{"member_name": "Alice", "pizza_id": pizza_id}]},
    )
    body = _assert_error(
        r, 429, "rate_limited",
        "Too many requests. Please wait 5 seconds before trying again.",
    )
    assert body["params"] == {"seconds": 5}
    assert r.headers["Retry-After"]
    assert r.headers["X-RateLimit-Remaining"] == "0"


def test_unregistered_code_is_rejected():
    with pytest.raises(ValueError, match="Unregistered error code"):
        AppError(status_code=400, code="not_a_real_code", message="nope")


# ---------------------------------------------------------------------------
# Auth & passwords
# ---------------------------------------------------------------------------

def test_too_many_logins(client, seeded_config):
    for _ in range(5):
        client.post("/api/auth/login", json={"username": "john", "password": "nope"})
    r = client.post("/api/auth/login", json={"username": "john", "password": "nope"})
    _assert_error(r, 429, "too_many_logins", "Too many login attempts")


def test_current_password_incorrect(client, seeded_config, cpo_headers):
    r = client.post(
        "/api/cpo/change-password",
        json={"current_password": "wrongpass", "new_password": "brandnew4711"},
        headers=cpo_headers,
    )
    _assert_error(r, 401, "current_password_incorrect", "Current password is incorrect.")


def test_password_too_common(client, seeded_config, cpo_headers):
    from tests.conftest import CPO_PASSWORD
    r = client.post(
        "/api/cpo/change-password",
        json={"current_password": CPO_PASSWORD, "new_password": "password"},
        headers=cpo_headers,
    )
    _assert_error(
        r, 422, "password_too_common",
        "Password is too common. Please choose a more unique password.",
    )


def test_password_contains_username(client, seeded_config, cpo_headers):
    from tests.conftest import CPO_PASSWORD
    r = client.post(
        "/api/cpo/change-password",
        json={"current_password": CPO_PASSWORD, "new_password": "myjohnpass"},
        headers=cpo_headers,
    )
    _assert_error(
        r, 422, "password_contains_username", "Password must not contain your username."
    )


def test_password_contains_app_name(client, seeded_config, admin_headers):
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
    _assert_error(
        r, 422, "password_contains_app_name",
        "Password must not contain words related to the application name, like pizza or cpo.",
    )


# ---------------------------------------------------------------------------
# Admin panel
# ---------------------------------------------------------------------------

def test_username_exists(client, seeded_config, admin_headers):
    r = client.post(
        "/api/admin/cpos",
        json={
            "username": "john",
            "email": "other@example.com",
            "team_name": "Sales",
            "initial_password": "fresh4711pass",
        },
        headers=admin_headers,
    )
    _assert_error(r, 409, "username_exists", "Username already exists")


def test_email_exists(client, seeded_config, admin_headers):
    r = client.post(
        "/api/admin/cpos",
        json={
            "username": "brandnew",
            "email": "john@example.com",
            "team_name": "Sales",
            "initial_password": "fresh4711pass",
        },
        headers=admin_headers,
    )
    _assert_error(r, 409, "email_exists", "Email already exists")


def test_cpo_not_found(client, seeded_config, admin_headers):
    r = client.put(
        "/api/admin/cpos/nosuchcpo", json={"email": "x@example.com"}, headers=admin_headers
    )
    _assert_error(r, 404, "cpo_not_found", "CPO not found")


def test_team_not_found(client, seeded_config, admin_headers):
    r = client.put(
        "/api/admin/teams/nosuchteam", json={"team_name": "Nope"}, headers=admin_headers
    )
    _assert_error(r, 404, "team_not_found", "Team not found")


def test_admin_not_found(client, seeded_config, admin_headers):
    r = client.delete("/api/admin/admins/999", headers=admin_headers)
    _assert_error(r, 404, "admin_not_found", "Admin not found")


def test_cannot_delete_self(client, seeded_config, admin_headers):
    r = client.delete("/api/admin/admins/1", headers=admin_headers)
    _assert_error(r, 403, "cannot_delete_self", "You cannot delete your own account")


def test_use_change_password(client, seeded_config, admin_headers):
    r = client.post(
        "/api/admin/admins/1/reset-password",
        json={"new_password": "another4711pass"},
        headers=admin_headers,
    )
    _assert_error(
        r, 403, "use_change_password", "Use change password to update your own password"
    )


def test_last_admin(client, seeded_config):
    """Unreachable over HTTP — the self-delete guard fires first for the only
    admin left — so the service is exercised directly."""
    with pytest.raises(AppError) as exc:
        admin_service.delete_admin(actor_id=999, admin_id=1)
    assert exc.value.code == "last_admin"
    assert exc.value.detail == "Cannot delete the last admin account"


# ---------------------------------------------------------------------------
# Team members & invites
# ---------------------------------------------------------------------------

def test_team_member_not_found(client, seeded_config, cpo_headers):
    r = client.delete("/api/cpo/team-members/nosuchmember", headers=cpo_headers)
    _assert_error(r, 404, "team_member_not_found", "Team member not found")


def test_last_team_member(client, seeded_config, cpo_headers):
    r = client.delete(f"/api/cpo/team-members/{seeded_config['cpo_id']}", headers=cpo_headers)
    _assert_error(r, 409, "last_team_member", "Cannot remove the last member of a team")


def test_invite_not_found(client, seeded_config, cpo_headers):
    r = client.delete("/api/cpo/team-invites/nosuchinvite", headers=cpo_headers)
    _assert_error(r, 404, "invite_not_found", "Invite not found")


def test_invite_invalid(client, seeded_config):
    r = client.get("/api/join/nosuchtoken")
    _assert_error(r, 404, "invite_invalid", "Invite link not found or expired")


def test_invite_used(client, seeded_config, cpo_headers, monkeypatch):
    """Only reachable when two redemptions race — mark_invite_used returning
    False is exactly what the loser of that race sees."""
    token = client.post("/api/cpo/team-invites", headers=cpo_headers).json()["token"]
    monkeypatch.setattr(team_service, "mark_invite_used", lambda *a, **kw: False)
    r = client.post(
        f"/api/join/{token}",
        json={"username": "jane", "email": "jane@example.com", "password": "joiner4711"},
    )
    _assert_error(r, 409, "invite_used", "Invite link already used")


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

def test_no_menus(client, seeded_config, cpo_headers):
    r = _open_session(client, cpo_headers)
    _assert_error(r, 422, "no_menus", "Create a menu before opening a session.")


def test_end_before_start(client, seeded_config, seeded_menu, cpo_headers):
    r = _open_session(client, cpo_headers, start_time="12:00", end_time="11:00")
    _assert_error(
        r, 422, "end_before_start",
        "End time must be after start time. Sessions spanning midnight are not supported yet.",
    )


def test_session_end_passed(client, seeded_config, seeded_menu, cpo_headers):
    r = _open_session(client, cpo_headers, session_date="2020-01-01")
    _assert_error(
        r, 422, "session_end_passed",
        "Session end time has already passed. Please set a future end time.",
    )


def test_session_already_open(client, seeded_config, seeded_menu, cpo_headers):
    assert _open_session(client, cpo_headers).status_code == 201
    r = _open_session(client, cpo_headers)
    _assert_error(
        r, 409, "session_already_open", "Team already has an active or upcoming session"
    )


def test_session_not_found(client, seeded_config, cpo_headers):
    r = client.get(f"/api/cpo/sessions/{_UNKNOWN_UUID}/summary", headers=cpo_headers)
    _assert_error(r, 404, "session_not_found", "Session not found")


def test_session_already_closed(client, seeded_config, seeded_menu, cpo_headers):
    session_id = _open_session(client, cpo_headers).json()["id"]
    assert client.post(f"/api/cpo/sessions/{session_id}/close", headers=cpo_headers).status_code == 200
    r = client.post(f"/api/cpo/sessions/{session_id}/close", headers=cpo_headers)
    _assert_error(r, 409, "session_already_closed", "Session is already closed")


# ---------------------------------------------------------------------------
# Menus & items
# ---------------------------------------------------------------------------

def test_menu_not_found_on_lookup(client, seeded_config, cpo_headers):
    r = client.get(f"/api/cpo/menus/{_UNKNOWN_UUID}/pizzas", headers=cpo_headers)
    _assert_error(r, 404, "menu_not_found", "Menu not found")


def test_menu_not_found_on_session_create(client, seeded_config, seeded_menu, cpo_headers):
    """Same message, same code — a different status (422, it is form input)."""
    r = _open_session(client, cpo_headers, menu_id=_UNKNOWN_UUID)
    _assert_error(r, 422, "menu_not_found", "Menu not found")


def test_menu_name_required(client, seeded_config, cpo_headers):
    r = client.post("/api/cpo/menus", json={"name": "   "}, headers=cpo_headers)
    _assert_error(r, 422, "menu_name_required", "Menu name is required")


def test_menu_name_exists(client, seeded_config, seeded_menu, cpo_headers):
    r = client.post("/api/cpo/menus", json={"name": seeded_menu.name}, headers=cpo_headers)
    _assert_error(r, 409, "menu_name_exists", "Menu name already exists")


def test_menu_in_use(client, seeded_config, seeded_menu, cpo_headers):
    assert _open_session(client, cpo_headers).status_code == 201
    r = client.delete(f"/api/cpo/menus/{seeded_menu.id}", headers=cpo_headers)
    _assert_error(
        r, 409, "menu_in_use", "Menu is used by an active or upcoming session"
    )


def test_menu_import_duplicate_name(client, seeded_config, seeded_menu, cpo_headers):
    r = client.post(
        f"/api/cpo/menus/{seeded_menu.id}/import",
        json={"dishes": [{"name": "Quattro", "price": 1.0}, {"name": "quattro", "price": 2.0}]},
        headers=cpo_headers,
    )
    body = _assert_error(
        r, 422, "menu_import_duplicate_name", "Duplicate dish name in import: 'quattro'"
    )
    # The clashing name travels as a param, so the sentence around it translates.
    assert body["params"] == {"name": "quattro"}


def test_pizza_name_exists(client, seeded_config, seeded_menu, cpo_headers):
    r = client.post(
        f"/api/cpo/menus/{seeded_menu.id}/pizzas",
        json={"name": "Margherita", "price": 11.0},
        headers=cpo_headers,
    )
    _assert_error(r, 409, "pizza_name_exists", "Pizza name already exists")


def test_pizza_not_found(client, seeded_config, seeded_menu, cpo_headers):
    r = client.delete(
        f"/api/cpo/menus/{seeded_menu.id}/pizzas/nosuchpizza", headers=cpo_headers
    )
    _assert_error(r, 404, "pizza_not_found", "Pizza not found")


def test_order_not_found(client, seeded_config, cpo_headers):
    r = client.delete("/api/cpo/orders/nosuchorder", headers=cpo_headers)
    _assert_error(r, 404, "order_not_found", "Order not found")


# ---------------------------------------------------------------------------
# Public ordering page
# ---------------------------------------------------------------------------

def test_team_link_not_found(client, seeded_config):
    r = client.get("/api/orders/nosuchlink")
    _assert_error(r, 404, "team_link_not_found", "Team link not found")


def test_session_closed(client, seeded_config, seeded_menu):
    """No session at all is "closed" as far as the ordering page is concerned."""
    r = _submit(client, seeded_config, "Alice", seeded_menu.pizzas[0].id)
    _assert_error(r, 403, "session_closed", "Session is closed")


def test_name_required(client, seeded_config, seeded_menu):
    _active_session(seeded_config, seeded_menu.id)
    r = _submit(client, seeded_config, "   ", seeded_menu.pizzas[0].id)
    _assert_error(r, 400, "name_required", "Name is required.")


def test_email_required(client, seeded_config, seeded_menu):
    _active_session(seeded_config, seeded_menu.id)
    _email_mode(seeded_config)
    r = _submit(client, seeded_config, "   ", seeded_menu.pizzas[0].id)
    _assert_error(r, 400, "email_required", "Email address is required.")


def test_email_too_long():
    """Unreachable over HTTP — OrderItem.member_name caps at the same 254 — so
    the service-level guard behind it is exercised directly."""
    with pytest.raises(AppError) as exc:
        order_service._normalize_member_value("a" * 250 + "@example.com", "email")
    assert exc.value.code == "email_too_long"
    assert exc.value.detail == "Email address must be 254 characters or fewer."
    assert exc.value.params == {"max": 254}


def test_invalid_email(client, seeded_config, seeded_menu):
    _active_session(seeded_config, seeded_menu.id)
    _email_mode(seeded_config)
    r = _submit(client, seeded_config, "not-an-email", seeded_menu.pizzas[0].id)
    body = _assert_error(
        r, 400, "invalid_email", "'not-an-email' is not a valid email address."
    )
    assert body["params"] == {"value": "not-an-email"}


def test_pizza_not_in_menu(client, seeded_config, seeded_menu):
    _active_session(seeded_config, seeded_menu.id)
    r = _submit(client, seeded_config, "Alice", "nosuchpizza")
    body = _assert_error(
        r, 400, "pizza_not_in_menu", "Pizza 'nosuchpizza' not found in menu"
    )
    assert body["params"] == {"pizza": "nosuchpizza"}


# ---------------------------------------------------------------------------
# Back-end ↔ front-end parity
# ---------------------------------------------------------------------------

def test_every_code_has_an_english_translation():
    """The guard that stops the two halves of the stack drifting apart: a code
    with no `errors.<code>` entry would show English in every language."""
    errors = json.loads(_EN_LOCALE.read_text(encoding="utf-8"))["errors"]
    missing = sorted(
        code for code in CODES
        if not isinstance(errors.get(code), str) or not errors[code].strip()
    )
    assert missing == []
