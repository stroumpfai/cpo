"""
Tests for the public order endpoints (Phase 5):
  GET  /api/orders/{unique_link}
  POST /api/orders/{unique_link}/submit
"""
from datetime import date, datetime, timedelta, timezone

def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc).replace(tzinfo=None)

import pytest

import storage
from models import Menu, Pizza, SessionFile
from services import order_service
from utils import new_id

# Fixtures from conftest.py: client, seeded_config, tmp_storage

_FUTURE = (date.today() + timedelta(days=1)).isoformat()
_PAST = "2020-01-01"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _default_menu(cpo_id: str) -> Menu:
    """Get-or-create the CPO's default menu."""
    menu = storage.get_default_menu(cpo_id)
    if menu is None:
        menu = storage.create_menu(cpo_id, "Default")
    return menu


def _add_active_session(seeded_config, menu_id: str | None = "default") -> SessionFile:
    """Save a session whose time window covers right now (start 00:00, end 23:59).

    menu_id: "default" links the session to the CPO's default menu (creating it
    if needed); None saves a legacy session without a menu reference.
    """
    cpo_id = seeded_config["cpo_id"]
    if menu_id == "default":
        menu_id = _default_menu(cpo_id).id
    session = SessionFile(
        id=new_id(),
        cpo_id=cpo_id,
        team_name="Engineering",
        session_date=_utcnow().date(),
        start_time="00:00",
        end_time="23:59",
        grace_period_minutes=2,
        created_at=datetime.now(tz=timezone.utc),
        menu_id=menu_id,
    )
    storage.save_session(session)
    return session


def _add_closed_session(seeded_config) -> SessionFile:
    cpo_id = seeded_config["cpo_id"]
    session = SessionFile(
        id=new_id(),
        cpo_id=cpo_id,
        team_name="Engineering",
        session_date=date(2020, 1, 1),
        start_time="11:00",
        end_time="12:00",
        grace_period_minutes=2,
        created_at=datetime.now(tz=timezone.utc),
        menu_id=_default_menu(cpo_id).id,
    )
    storage.save_session(session)
    return session


def _add_pizza(seeded_config, name: str = "Margherita", price: float = 12.50) -> Pizza:
    cpo_id = seeded_config["cpo_id"]
    menu = _default_menu(cpo_id)
    pizza = Pizza(id=new_id(), name=name, price=price)
    menu.pizzas.append(pizza)
    storage.save_menu(menu)
    return pizza


def _unique_link(seeded_config) -> str:
    return seeded_config["cpo"].unique_link


# ---------------------------------------------------------------------------
# GET /api/orders/{unique_link}
# ---------------------------------------------------------------------------

def test_get_status_unknown_link(client, seeded_config):
    r = client.get("/api/orders/unknownlink12345")
    assert r.status_code == 404


def test_get_status_no_sessions(client, seeded_config):
    link = _unique_link(seeded_config)
    r = client.get(f"/api/orders/{link}")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "closed"
    assert body["pizzas"] == []
    assert body["message"] == "No active session"


def test_get_status_closed_session(client, seeded_config):
    _add_closed_session(seeded_config)
    link = _unique_link(seeded_config)
    r = client.get(f"/api/orders/{link}")
    assert r.status_code == 200
    assert r.json()["status"] == "closed"
    assert r.json()["message"] == "Session is closed"


def test_get_status_active_session_includes_menu(client, seeded_config):
    _add_active_session(seeded_config)
    _add_pizza(seeded_config)
    link = _unique_link(seeded_config)
    r = client.get(f"/api/orders/{link}")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "active"
    assert len(body["pizzas"]) == 1
    assert body["pizzas"][0]["name"] == "Margherita"
    assert body["message"] is None


def test_get_status_returns_team_name(client, seeded_config):
    _add_active_session(seeded_config)
    link = _unique_link(seeded_config)
    r = client.get(f"/api/orders/{link}")
    assert r.json()["team_name"] == "Engineering"


def _add_pizzeria_url(seeded_config, url: str) -> None:
    cpo_id = seeded_config["cpo_id"]
    menu = _default_menu(cpo_id)
    menu.pizzeria_url = url
    storage.save_menu(menu)


def test_get_status_includes_pizzeria_url(client, seeded_config):
    _add_active_session(seeded_config)
    _add_pizzeria_url(seeded_config, "https://pizzeria.example.com")
    link = _unique_link(seeded_config)
    r = client.get(f"/api/orders/{link}")
    assert r.status_code == 200
    assert r.json()["pizzeria_url"] == "https://pizzeria.example.com"


def test_get_status_pizzeria_url_null_when_not_set(client, seeded_config):
    _add_active_session(seeded_config)
    link = _unique_link(seeded_config)
    r = client.get(f"/api/orders/{link}")
    assert r.json()["pizzeria_url"] is None


def test_get_status_includes_currency(client, seeded_config):
    link = _unique_link(seeded_config)
    r = client.get(f"/api/orders/{link}")
    assert r.status_code == 200
    assert r.json()["currency"] == "CHF"


def _set_email_mode(seeded_config) -> None:
    """Flip the seeded CPO into email mode through the storage layer."""
    cfg = storage.load_config()
    next(c for c in cfg.cpos if c.id == seeded_config["cpo_id"]).member_identifier = "email"
    storage.save_config(cfg)


def test_get_status_includes_member_identifier_default_name(client, seeded_config):
    _add_active_session(seeded_config)
    r = client.get(f"/api/orders/{_unique_link(seeded_config)}")
    assert r.status_code == 200
    assert r.json()["member_identifier"] == "name"


def test_get_status_reflects_email_mode(client, seeded_config):
    _add_active_session(seeded_config)
    _set_email_mode(seeded_config)
    r = client.get(f"/api/orders/{_unique_link(seeded_config)}")
    assert r.json()["member_identifier"] == "email"


def test_get_status_includes_member_identifier_with_no_session(client, seeded_config):
    """The no-session branch builds its own response object — it must carry the field too."""
    _set_email_mode(seeded_config)
    r = client.get(f"/api/orders/{_unique_link(seeded_config)}")
    assert r.json()["message"] == "No active session"
    assert r.json()["member_identifier"] == "email"


# ---------------------------------------------------------------------------
# POST /api/orders/{unique_link}/submit
# ---------------------------------------------------------------------------

def test_submit_order_success(client, seeded_config):
    order_service.clear_rate_limit()
    _add_active_session(seeded_config)
    pizza = _add_pizza(seeded_config)
    link = _unique_link(seeded_config)

    r = client.post(
        f"/api/orders/{link}/submit",
        json={"items": [{"member_name": "Alice", "pizza_id": pizza.id}]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "submitted"
    assert body["orders_created"] == 1
    assert len(body["order_ids"]) == 1


def test_submit_multiple_pizzas(client, seeded_config):
    order_service.clear_rate_limit()
    _add_active_session(seeded_config)
    pizza = _add_pizza(seeded_config)
    p2 = _add_pizza(seeded_config, name="Pepperoni", price=13.50)

    link = _unique_link(seeded_config)
    r = client.post(
        f"/api/orders/{link}/submit",
        json={"items": [{"member_name": "Bob", "pizza_id": pizza.id}, {"member_name": "Bob", "pizza_id": p2.id}]},
    )
    assert r.status_code == 200
    assert r.json()["orders_created"] == 2


def test_submit_order_creates_records_in_session(client, seeded_config):
    order_service.clear_rate_limit()
    session = _add_active_session(seeded_config)
    pizza = _add_pizza(seeded_config)
    link = _unique_link(seeded_config)

    client.post(
        f"/api/orders/{link}/submit",
        json={"items": [{"member_name": "Alice", "pizza_id": pizza.id}]},
    )

    loaded = storage.load_session(seeded_config["cpo_id"], session.id)
    assert len(loaded.orders) == 1
    assert loaded.orders[0].member_name == "Alice"
    assert loaded.orders[0].pizza_name == "Margherita"


def test_submit_to_closed_session(client, seeded_config):
    order_service.clear_rate_limit()
    _add_closed_session(seeded_config)
    pizza = _add_pizza(seeded_config)
    link = _unique_link(seeded_config)

    r = client.post(
        f"/api/orders/{link}/submit",
        json={"items": [{"member_name": "Alice", "pizza_id": pizza.id}]},
    )
    assert r.status_code == 403


def test_submit_unknown_pizza_id(client, seeded_config):
    order_service.clear_rate_limit()
    _add_active_session(seeded_config)
    link = _unique_link(seeded_config)

    r = client.post(
        f"/api/orders/{link}/submit",
        json={"items": [{"member_name": "Alice", "pizza_id": "bad-pizza-id"}]},
    )
    assert r.status_code == 400


def test_submit_empty_member_name(client, seeded_config):
    order_service.clear_rate_limit()
    _add_active_session(seeded_config)
    pizza = _add_pizza(seeded_config)
    link = _unique_link(seeded_config)

    r = client.post(
        f"/api/orders/{link}/submit",
        json={"items": [{"member_name": "", "pizza_id": pizza.id}]},
    )
    assert r.status_code == 422


def test_submit_empty_pizza_list(client, seeded_config):
    order_service.clear_rate_limit()
    _add_active_session(seeded_config)
    link = _unique_link(seeded_config)

    r = client.post(
        f"/api/orders/{link}/submit",
        json={"items": []},
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Comment field
# ---------------------------------------------------------------------------

def test_submit_with_comment_stored(client, seeded_config):
    order_service.clear_rate_limit()
    session = _add_active_session(seeded_config)
    pizza = _add_pizza(seeded_config)
    link = _unique_link(seeded_config)

    client.post(
        f"/api/orders/{link}/submit",
        json={"items": [{"member_name": "Alice", "pizza_id": pizza.id, "comment": "no olives"}]},
    )

    loaded = storage.load_session(seeded_config["cpo_id"], session.id)
    assert loaded.orders[0].comment == "no olives"


def test_submit_comment_too_long_returns_422(client, seeded_config):
    order_service.clear_rate_limit()
    _add_active_session(seeded_config)
    pizza = _add_pizza(seeded_config)
    link = _unique_link(seeded_config)

    r = client.post(
        f"/api/orders/{link}/submit",
        json={"items": [{"member_name": "Alice", "pizza_id": pizza.id, "comment": "x" * 101}]},
    )
    assert r.status_code == 422


def test_submit_empty_string_comment_returns_422(client, seeded_config):
    order_service.clear_rate_limit()
    _add_active_session(seeded_config)
    pizza = _add_pizza(seeded_config)
    link = _unique_link(seeded_config)

    r = client.post(
        f"/api/orders/{link}/submit",
        json={"items": [{"member_name": "Alice", "pizza_id": pizza.id, "comment": ""}]},
    )
    assert r.status_code == 422


def test_submit_without_comment_field_backward_compat(client, seeded_config):
    order_service.clear_rate_limit()
    session = _add_active_session(seeded_config)
    pizza = _add_pizza(seeded_config)
    link = _unique_link(seeded_config)

    r = client.post(
        f"/api/orders/{link}/submit",
        json={"items": [{"member_name": "Alice", "pizza_id": pizza.id}]},
    )
    assert r.status_code == 200
    loaded = storage.load_session(seeded_config["cpo_id"], session.id)
    assert loaded.orders[0].comment is None


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

def test_rate_limit_second_request_within_window(client, seeded_config):
    order_service.clear_rate_limit()
    _add_active_session(seeded_config)
    pizza = _add_pizza(seeded_config)
    link = _unique_link(seeded_config)
    payload = {"items": [{"member_name": "Alice", "pizza_id": pizza.id}]}

    r1 = client.post(f"/api/orders/{link}/submit", json=payload)
    assert r1.status_code == 200

    # Same IP, immediate second request → rate limited
    r2 = client.post(f"/api/orders/{link}/submit", json=payload)
    assert r2.status_code == 429
    assert "X-RateLimit-Limit" in r2.headers
    assert "Retry-After" in r2.headers


def test_rate_limit_resets_after_window(client, seeded_config):
    order_service.clear_rate_limit()
    _add_active_session(seeded_config)
    pizza = _add_pizza(seeded_config)
    link = _unique_link(seeded_config)
    payload = {"items": [{"member_name": "Alice", "pizza_id": pizza.id}]}

    r1 = client.post(f"/api/orders/{link}/submit", json=payload)
    assert r1.status_code == 200

    # Backdate every IP's last-seen timestamp by 10 s so the window has expired
    for ip in order_service._rate_limit:
        order_service._rate_limit[ip] -= 10

    r2 = client.post(f"/api/orders/{link}/submit", json=payload)
    assert r2.status_code == 200  # window has passed


def test_rate_limit_unknown_link(client, seeded_config):
    """Rate limit check fires even before session lookup."""
    order_service.clear_rate_limit()
    r1 = client.post("/api/orders/unknownlink12345/submit", json={"items": [{"member_name": "X", "pizza_id": "y"}]})
    # First attempt: link not found (404), but rate limit slot consumed
    assert r1.status_code == 404

    r2 = client.post("/api/orders/unknownlink12345/submit", json={"items": [{"member_name": "X", "pizza_id": "y"}]})
    assert r2.status_code == 429


# ---------------------------------------------------------------------------
# Multi-menu: sessions serve their own menu
# ---------------------------------------------------------------------------

def _add_second_menu_with_pizza(seeded_config) -> tuple[Menu, Pizza]:
    cpo_id = seeded_config["cpo_id"]
    _default_menu(cpo_id)   # ensure the default exists first
    menu = storage.create_menu(cpo_id, "Thai", pizzeria_url="https://thai.example.com")
    pizza = Pizza(id=new_id(), name="Pad Thai", price=16.00)
    menu.pizzas.append(pizza)
    storage.save_menu(menu)
    return menu, pizza


def test_get_status_serves_session_menu_not_default(client, seeded_config):
    """A session linked to a non-default menu serves that menu's items and url."""
    _add_pizza(seeded_config)   # goes into the default menu
    menu, _ = _add_second_menu_with_pizza(seeded_config)
    _add_active_session(seeded_config, menu_id=menu.id)

    r = client.get(f"/api/orders/{_unique_link(seeded_config)}")
    assert r.status_code == 200
    body = r.json()
    assert [p["name"] for p in body["pizzas"]] == ["Pad Thai"]
    assert body["pizzeria_url"] == "https://thai.example.com"


def test_submit_pizza_from_other_menu_rejected(client, seeded_config):
    """A pizza id from a menu the session does not serve → 400."""
    order_service.clear_rate_limit()
    default_pizza = _add_pizza(seeded_config)
    menu, _ = _add_second_menu_with_pizza(seeded_config)
    _add_active_session(seeded_config, menu_id=menu.id)

    r = client.post(
        f"/api/orders/{_unique_link(seeded_config)}/submit",
        json={"items": [{"member_name": "Alice", "pizza_id": default_pizza.id}]},
    )
    assert r.status_code == 400


def test_submit_from_session_menu_succeeds(client, seeded_config):
    order_service.clear_rate_limit()
    _add_pizza(seeded_config)
    menu, thai_pizza = _add_second_menu_with_pizza(seeded_config)
    _add_active_session(seeded_config, menu_id=menu.id)

    r = client.post(
        f"/api/orders/{_unique_link(seeded_config)}/submit",
        json={"items": [{"member_name": "Alice", "pizza_id": thai_pizza.id}]},
    )
    assert r.status_code == 200
    assert r.json()["orders_created"] == 1


def test_legacy_session_without_menu_falls_back_to_default(client, seeded_config):
    """Sessions saved before multi-menu (menu_id NULL) keep serving the default menu."""
    order_service.clear_rate_limit()
    pizza = _add_pizza(seeded_config)
    _add_second_menu_with_pizza(seeded_config)
    _add_active_session(seeded_config, menu_id=None)

    link = _unique_link(seeded_config)
    r = client.get(f"/api/orders/{link}")
    assert [p["name"] for p in r.json()["pizzas"]] == ["Margherita"]

    r = client.post(
        f"/api/orders/{link}/submit",
        json={"items": [{"member_name": "Alice", "pizza_id": pizza.id}]},
    )
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# Member identifier: email mode
# ---------------------------------------------------------------------------

def _submit(client, seeded_config, member_name: str, pizza_id: str):
    return client.post(
        f"/api/orders/{_unique_link(seeded_config)}/submit",
        json={"items": [{"member_name": member_name, "pizza_id": pizza_id}]},
    )


def test_submit_order_accepts_valid_email_in_email_mode(client, seeded_config):
    order_service.clear_rate_limit()
    session = _add_active_session(seeded_config)
    pizza = _add_pizza(seeded_config)
    _set_email_mode(seeded_config)

    r = _submit(client, seeded_config, "alice@example.com", pizza.id)
    assert r.status_code == 200
    loaded = storage.load_session(seeded_config["cpo_id"], session.id)
    assert loaded.orders[0].member_name == "alice@example.com"


def test_submit_order_rejects_invalid_email_in_email_mode(client, seeded_config):
    order_service.clear_rate_limit()
    _add_active_session(seeded_config)
    pizza = _add_pizza(seeded_config)
    _set_email_mode(seeded_config)

    r = _submit(client, seeded_config, "not-an-email", pizza.id)
    assert r.status_code == 400
    assert "not a valid email address" in r.json()["detail"]


def test_submit_order_rejects_plain_name_in_email_mode(client, seeded_config):
    order_service.clear_rate_limit()
    _add_active_session(seeded_config)
    pizza = _add_pizza(seeded_config)
    _set_email_mode(seeded_config)

    assert _submit(client, seeded_config, "Alice", pizza.id).status_code == 400


def test_submit_order_lowercases_email(client, seeded_config):
    """The dashboard's distinct-member count is a case-sensitive Set, so
    Alice@Example.COM and alice@example.com must collapse to one person."""
    order_service.clear_rate_limit()
    session = _add_active_session(seeded_config)
    pizza = _add_pizza(seeded_config)
    _set_email_mode(seeded_config)

    r = _submit(client, seeded_config, "Alice@Example.COM", pizza.id)
    assert r.status_code == 200
    loaded = storage.load_session(seeded_config["cpo_id"], session.id)
    assert loaded.orders[0].member_name == "alice@example.com"


def test_submit_order_email_validation_does_not_hit_dns(client, seeded_config, monkeypatch):
    """validate_email defaults to check_deliverability=True, which would fire a
    DNS MX lookup per cart item. Pin the flag so nobody drops it."""
    order_service.clear_rate_limit()
    _add_active_session(seeded_config)
    pizza = _add_pizza(seeded_config)
    _set_email_mode(seeded_config)

    calls = []
    real = order_service.validate_email

    def spy(value, **kwargs):
        calls.append(kwargs)
        return real(value, **kwargs)

    monkeypatch.setattr(order_service, "validate_email", spy)
    assert _submit(client, seeded_config, "alice@example.com", pizza.id).status_code == 200
    assert calls == [{"check_deliverability": False}]


def test_submit_order_accepts_email_over_100_chars_in_email_mode(client, seeded_config):
    """Real corporate addresses exceed the old 100-char member_name cap."""
    order_service.clear_rate_limit()
    session = _add_active_session(seeded_config)
    pizza = _add_pizza(seeded_config)
    _set_email_mode(seeded_config)

    long_email = "firstname.lastname" + ("x" * 60) + "@team.division.company-group.example.com"
    assert len(long_email) > 100
    r = _submit(client, seeded_config, long_email, pizza.id)
    assert r.status_code == 200
    loaded = storage.load_session(seeded_config["cpo_id"], session.id)
    assert loaded.orders[0].member_name == long_email


def test_submit_order_persists_nothing_when_one_email_is_invalid(client, seeded_config):
    order_service.clear_rate_limit()
    session = _add_active_session(seeded_config)
    pizza = _add_pizza(seeded_config)
    _set_email_mode(seeded_config)

    r = client.post(
        f"/api/orders/{_unique_link(seeded_config)}/submit",
        json={"items": [
            {"member_name": "alice@example.com", "pizza_id": pizza.id},
            {"member_name": "broken", "pizza_id": pizza.id},
        ]},
    )
    assert r.status_code == 400
    loaded = storage.load_session(seeded_config["cpo_id"], session.id)
    assert loaded.orders == []


def test_submit_order_invalid_email_still_consumes_rate_limit(client, seeded_config):
    """The slot is consumed before validation on purpose — refunding it would
    turn the endpoint into a free email-validation oracle."""
    order_service.clear_rate_limit()
    _add_active_session(seeded_config)
    pizza = _add_pizza(seeded_config)
    _set_email_mode(seeded_config)

    assert _submit(client, seeded_config, "broken", pizza.id).status_code == 400
    assert _submit(client, seeded_config, "alice@example.com", pizza.id).status_code == 429


# ---------------------------------------------------------------------------
# Member identifier: name mode normalisation
# ---------------------------------------------------------------------------

def test_submit_order_accepts_non_email_string_in_name_mode(client, seeded_config):
    """Regression guard: the default mode must be completely unaffected."""
    order_service.clear_rate_limit()
    _add_active_session(seeded_config)
    pizza = _add_pizza(seeded_config)

    assert _submit(client, seeded_config, "Alice", pizza.id).status_code == 200


def test_submit_order_strips_whitespace_from_member_name(client, seeded_config):
    order_service.clear_rate_limit()
    session = _add_active_session(seeded_config)
    pizza = _add_pizza(seeded_config)

    assert _submit(client, seeded_config, "  Alice  ", pizza.id).status_code == 200
    loaded = storage.load_session(seeded_config["cpo_id"], session.id)
    assert loaded.orders[0].member_name == "Alice"


def test_submit_order_rejects_whitespace_only_member_name(client, seeded_config):
    """Previously stored a literal space and returned 200."""
    order_service.clear_rate_limit()
    _add_active_session(seeded_config)
    pizza = _add_pizza(seeded_config)

    r = _submit(client, seeded_config, "   ", pizza.id)
    assert r.status_code == 400
    assert r.json()["detail"] == "Name is required."


def test_submit_order_rejects_name_over_100_chars_in_name_mode(client, seeded_config):
    order_service.clear_rate_limit()
    _add_active_session(seeded_config)
    pizza = _add_pizza(seeded_config)

    r = _submit(client, seeded_config, "A" * 101, pizza.id)
    assert r.status_code == 400
    assert "100 characters or fewer" in r.json()["detail"]
