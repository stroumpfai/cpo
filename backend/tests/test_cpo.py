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
# POST /api/cpo/sessions
# ---------------------------------------------------------------------------

SESSION_BODY = {
    "session_date": _FUTURE,
    "start_time": "11:30",
    "end_time": "12:00",
    "grace_period_minutes": 2,
}


def test_create_session_success(client, seeded_config, cpo_headers):
    r = client.post("/api/cpo/sessions", json=SESSION_BODY, headers=cpo_headers)
    assert r.status_code == 201
    body = r.json()
    assert body["start_time"] == "11:30"
    assert body["end_time"] == "12:00"
    assert body["team_name"] == "Engineering"
    assert "unique_link" in body
    assert "id" in body


def test_create_session_includes_status(client, seeded_config, cpo_headers):
    r = client.post("/api/cpo/sessions", json=SESSION_BODY, headers=cpo_headers)
    assert r.status_code == 201
    assert r.json()["status"] in ("upcoming", "active", "closed")


def test_create_second_active_session_rejected(client, seeded_config, cpo_headers):
    # First session: upcoming (start time in the future)
    r1 = client.post("/api/cpo/sessions", json=SESSION_BODY, headers=cpo_headers)
    assert r1.status_code == 201
    # Second session should be rejected
    r2 = client.post("/api/cpo/sessions", json={**SESSION_BODY, "start_time": "13:00", "end_time": "14:00"}, headers=cpo_headers)
    assert r2.status_code == 409


def test_create_session_invalid_time(client, seeded_config, cpo_headers):
    r = client.post(
        "/api/cpo/sessions",
        json={**SESSION_BODY, "start_time": "99:99"},
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


def test_list_sessions_after_create(client, seeded_config, cpo_headers):
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

    cpo_id = seeded_config["cpo_id"]
    session = SessionFile(
        id=new_id(),
        cpo_id=cpo_id,
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
    r = client.get("/api/cpo/sessions/nonexistent/summary", headers=cpo_headers)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Menu CRUD
# ---------------------------------------------------------------------------

def test_menu_starts_empty(client, seeded_config, cpo_headers):
    r = client.get("/api/cpo/menu", headers=cpo_headers)
    assert r.status_code == 200
    assert r.json() == []


def test_add_pizza(client, seeded_config, cpo_headers):
    r = client.post("/api/cpo/menu", json={"name": "Margherita", "price": 12.50}, headers=cpo_headers)
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Margherita"
    assert body["price"] == pytest.approx(12.50, abs=1e-6)
    assert "id" in body


def test_add_pizza_duplicate_name(client, seeded_config, cpo_headers):
    client.post("/api/cpo/menu", json={"name": "Margherita", "price": 12.50}, headers=cpo_headers)
    r = client.post("/api/cpo/menu", json={"name": "Margherita", "price": 9.00}, headers=cpo_headers)
    assert r.status_code == 409


def test_add_pizza_case_insensitive_duplicate(client, seeded_config, cpo_headers):
    client.post("/api/cpo/menu", json={"name": "Margherita", "price": 12.50}, headers=cpo_headers)
    r = client.post("/api/cpo/menu", json={"name": "margherita", "price": 9.00}, headers=cpo_headers)
    assert r.status_code == 409


def test_add_pizza_invalid_price(client, seeded_config, cpo_headers):
    r = client.post("/api/cpo/menu", json={"name": "Free Pizza", "price": 0.0}, headers=cpo_headers)
    assert r.status_code == 422


def test_update_pizza(client, seeded_config, cpo_headers):
    create = client.post("/api/cpo/menu", json={"name": "Margherita", "price": 12.50}, headers=cpo_headers)
    pizza_id = create.json()["id"]
    r = client.put(f"/api/cpo/menu/{pizza_id}", json={"name": "Margherita Extra", "price": 14.00}, headers=cpo_headers)
    assert r.status_code == 200
    assert r.json()["name"] == "Margherita Extra"
    assert r.json()["price"] == pytest.approx(14.00, abs=1e-6)


def test_update_pizza_duplicate_name(client, seeded_config, cpo_headers):
    client.post("/api/cpo/menu", json={"name": "Margherita", "price": 12.50}, headers=cpo_headers)
    r2 = client.post("/api/cpo/menu", json={"name": "Pepperoni", "price": 13.00}, headers=cpo_headers)
    pizza_id = r2.json()["id"]
    r = client.put(f"/api/cpo/menu/{pizza_id}", json={"name": "Margherita", "price": 13.00}, headers=cpo_headers)
    assert r.status_code == 409


def test_update_pizza_same_name_allowed(client, seeded_config, cpo_headers):
    """Updating a pizza to keep the same name should succeed."""
    create = client.post("/api/cpo/menu", json={"name": "Margherita", "price": 12.50}, headers=cpo_headers)
    pizza_id = create.json()["id"]
    r = client.put(f"/api/cpo/menu/{pizza_id}", json={"name": "Margherita", "price": 15.00}, headers=cpo_headers)
    assert r.status_code == 200


def test_update_pizza_not_found(client, seeded_config, cpo_headers):
    r = client.put("/api/cpo/menu/nonexistent", json={"name": "X", "price": 10.0}, headers=cpo_headers)
    assert r.status_code == 404


def test_delete_pizza(client, seeded_config, cpo_headers):
    create = client.post("/api/cpo/menu", json={"name": "Margherita", "price": 12.50}, headers=cpo_headers)
    pizza_id = create.json()["id"]
    r = client.delete(f"/api/cpo/menu/{pizza_id}", headers=cpo_headers)
    assert r.status_code == 204
    # verify gone
    menu = client.get("/api/cpo/menu", headers=cpo_headers)
    assert menu.json() == []


def test_delete_pizza_not_found(client, seeded_config, cpo_headers):
    r = client.delete("/api/cpo/menu/nonexistent", headers=cpo_headers)
    assert r.status_code == 404


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
# Force-close session
# ---------------------------------------------------------------------------

def _active_session(seeded_config) -> SessionFile:
    now = _utcnow()
    session = SessionFile(
        id=new_id(),
        cpo_id=seeded_config["cpo_id"],
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


def test_close_session_allows_new_session(client, seeded_config, cpo_headers):
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
    r = client.post("/api/cpo/sessions/nonexistent/close", headers=cpo_headers)
    assert r.status_code == 404


def test_close_session_requires_cpo(client, seeded_config, admin_headers):
    session = _active_session(seeded_config)
    r = client.post(f"/api/cpo/sessions/{session.id}/close", headers=admin_headers)
    assert r.status_code == 403
