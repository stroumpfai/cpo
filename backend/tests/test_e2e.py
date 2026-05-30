"""
End-to-end integration tests.

Each test exercises a full user journey through the HTTP API without touching
storage internals directly, except where noted for edge-case time manipulation.

Flow: admin seeds config → admin creates CPO → CPO builds menu + session
      → team member visits link & submits orders → CPO inspects summary
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

def _utcnow() -> datetime:
    """Naive UTC datetime — matches now_utc() on the server."""
    return datetime.now(tz=timezone.utc).replace(tzinfo=None)

import pytest
from fastapi.testclient import TestClient

# Test-only credentials — not production secrets
_ADMIN_PW = "AdminSecurePass123"   # noqa: S105  # NOSONAR
_CPO_PW   = "TeamSecurePass123"   # noqa: S105  # NOSONAR

import config as cfg_module
import storage
from main import app
from models import AdminRecord, ConfigFile, SessionFile
from services import order_service
from utils import hash_password, new_id


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def e2e(tmp_path, monkeypatch):
    """Isolated storage with only the admin account pre-seeded. Returns a TestClient."""
    config_file = tmp_path / "config" / "config.json"
    data_dir    = tmp_path / "data"
    monkeypatch.setattr(storage,     "CONFIG_PATH", str(config_file))
    monkeypatch.setattr(cfg_module,  "CONFIG_PATH", str(config_file))
    monkeypatch.setattr(storage,     "DATA_DIR",    str(data_dir))
    monkeypatch.setattr(cfg_module,  "DATA_DIR",    str(data_dir))
    order_service.clear_rate_limit()

    admin = AdminRecord(
        username="admin",
        password_hash=hash_password(_ADMIN_PW),
        created_at=datetime.now(tz=timezone.utc),
    )
    storage.save_config(ConfigFile(admin=admin, cpos=[]))
    return TestClient(app)


# ---------------------------------------------------------------------------
# Shared setup helpers
# ---------------------------------------------------------------------------

def _admin_headers(client: TestClient) -> dict:
    r = client.post("/api/auth/login", json={"username": "admin", "password": _ADMIN_PW})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _create_cpo(client: TestClient, admin_h: dict) -> dict:
    r = client.post(
        "/api/admin/cpos",
        json={
            "username": "john",
            "email": "john@example.com",
            "team_name": "Engineering",
            "initial_password": _CPO_PW,
        },
        headers=admin_h,
    )
    assert r.status_code == 201
    return r.json()


def _cpo_headers(client: TestClient) -> dict:
    r = client.post("/api/auth/login", json={"username": "john", "password": _CPO_PW})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _add_pizza(client: TestClient, cpo_h: dict, name: str = "Margherita", price: float = 12.50) -> dict:
    r = client.post("/api/cpo/menu", json={"name": name, "price": price}, headers=cpo_h)
    assert r.status_code == 201
    return r.json()


def _create_active_session(client: TestClient, cpo_h: dict, grace: int = 2) -> dict:
    """Create a session whose window spans right now (UTC times submitted to API)."""
    now  = _utcnow()
    body = {
        "session_date": now.date().isoformat(),
        "start_time":   (now - timedelta(minutes=30)).strftime("%H:%M"),
        "end_time":     (now + timedelta(minutes=30)).strftime("%H:%M"),
        "grace_period_minutes": grace,
    }
    r = client.post("/api/cpo/sessions", json=body, headers=cpo_h)
    assert r.status_code == 201
    return r.json()


# ---------------------------------------------------------------------------
# 1. Happy-path end-to-end flow
# ---------------------------------------------------------------------------

def test_full_ordering_flow(e2e):
    client = e2e
    admin_h = _admin_headers(client)

    # Admin creates CPO
    cpo = _create_cpo(client, admin_h)
    unique_link = cpo["unique_link"]
    assert len(unique_link) >= 16

    # CPO logs in, adds a pizza, opens a session
    cpo_h = _cpo_headers(client)
    pizza  = _add_pizza(client, cpo_h)
    session = _create_active_session(client, cpo_h)
    assert session["status"] == "active"
    session_id = session["id"]

    # Team member sees active session + menu
    r = client.get(f"/api/orders/{unique_link}")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "active"
    assert len(body["pizzas"]) == 1
    assert body["pizzas"][0]["name"] == "Margherita"

    # Team member submits an order
    r = client.post(
        f"/api/orders/{unique_link}/submit",
        json={"items": [{"member_name": "Alice", "pizza_id": pizza["id"]}]},
    )
    assert r.status_code == 200
    assert r.json()["orders_created"] == 1

    # CPO checks summary
    r = client.get(f"/api/cpo/sessions/{session_id}/summary", headers=cpo_h)
    assert r.status_code == 200
    summary = r.json()
    assert summary["total_orders"] == 1
    assert summary["total_price"] == pytest.approx(12.50, abs=1e-6)
    assert summary["distribution"][0]["member_name"] == "Alice"
    assert summary["distribution"][0]["pizza_name"] == "Margherita"
    assert summary["pizzeria"][0]["count"] == 1

    # IP is captured
    assert summary["distribution"][0]["client_ip"] != ""

    # CPO deletes the order
    order_id = summary["distribution"][0]["order_id"]
    r = client.delete(f"/api/cpo/orders/{order_id}", headers=cpo_h)
    assert r.status_code == 204

    # Summary now empty
    r = client.get(f"/api/cpo/sessions/{session_id}/summary", headers=cpo_h)
    assert r.json()["total_orders"] == 0


# ---------------------------------------------------------------------------
# 2. Multi-pizza submission
# ---------------------------------------------------------------------------

def test_multi_pizza_submission(e2e):
    client = e2e
    admin_h = _admin_headers(client)
    cpo     = _create_cpo(client, admin_h)
    link    = cpo["unique_link"]
    cpo_h   = _cpo_headers(client)

    p1 = _add_pizza(client, cpo_h, "Margherita", 12.50)
    p2 = _add_pizza(client, cpo_h, "Pepperoni",  13.50)
    session = _create_active_session(client, cpo_h)

    r = client.post(
        f"/api/orders/{link}/submit",
        json={"items": [{"member_name": "Bob", "pizza_id": p1["id"]}, {"member_name": "Bob", "pizza_id": p2["id"]}]},
    )
    assert r.status_code == 200
    assert r.json()["orders_created"] == 2

    summary = client.get(f"/api/cpo/sessions/{session['id']}/summary", headers=cpo_h).json()
    assert summary["total_orders"] == 2
    assert summary["total_price"] == pytest.approx(26.00, abs=1e-6)
    pizza_names = {r["pizza_name"] for r in summary["distribution"]}
    assert pizza_names == {"Margherita", "Pepperoni"}


# ---------------------------------------------------------------------------
# 3. Rate limiting
# ---------------------------------------------------------------------------

def test_rate_limiting(e2e):
    client = e2e
    order_service.clear_rate_limit()
    admin_h = _admin_headers(client)
    cpo     = _create_cpo(client, admin_h)
    link    = cpo["unique_link"]
    cpo_h   = _cpo_headers(client)

    pizza = _add_pizza(client, cpo_h)
    _create_active_session(client, cpo_h)

    payload = {"items": [{"member_name": "Alice", "pizza_id": pizza["id"]}]}

    # First submission succeeds
    r1 = client.post(f"/api/orders/{link}/submit", json=payload)
    assert r1.status_code == 200

    # Second submission immediately after → rate limited
    r2 = client.post(f"/api/orders/{link}/submit", json=payload)
    assert r2.status_code == 429
    assert "X-RateLimit-Limit"     in r2.headers
    assert "X-RateLimit-Remaining" in r2.headers
    assert "Retry-After"           in r2.headers

    # After backdating the rate limit entry, submission succeeds again
    for ip in order_service._rate_limit:
        order_service._rate_limit[ip] -= 10   # simulate 10 s passing
    r3 = client.post(f"/api/orders/{link}/submit", json=payload)
    assert r3.status_code == 200


# ---------------------------------------------------------------------------
# 4. Grace period — order within 2 min of end_time is accepted
# ---------------------------------------------------------------------------

def test_grace_period_accepts_order(e2e):
    """Session ended 1 minute ago; 2-min grace still open → order accepted."""
    client = e2e
    order_service.clear_rate_limit()
    admin_h = _admin_headers(client)
    cpo     = _create_cpo(client, admin_h)
    link    = cpo["unique_link"]
    cpo_h   = _cpo_headers(client)
    pizza   = _add_pizza(client, cpo_h)

    # Create the session directly in storage (bypasses "no active session" API check)
    now       = _utcnow()
    cpo_id    = storage.load_config().cpos[0].id
    session   = SessionFile(
        id=new_id(),
        cpo_id=cpo_id,
        team_name="Engineering",
        session_date=now.date(),
        start_time=(now - timedelta(hours=1)).strftime("%H:%M"),
        end_time=(now - timedelta(minutes=1)).strftime("%H:%M"),   # ended 1 min ago
        grace_period_minutes=2,
        created_at=datetime.now(tz=timezone.utc),
    )
    storage.save_session(session)

    r = client.post(
        f"/api/orders/{link}/submit",
        json={"items": [{"member_name": "Alice", "pizza_id": pizza["id"]}]},
    )
    assert r.status_code == 200, f"Expected 200 (within grace), got {r.status_code}: {r.text}"


# ---------------------------------------------------------------------------
# 5. Grace period — order more than 2 min after end_time is rejected
# ---------------------------------------------------------------------------

def test_after_grace_period_rejects_order(e2e):
    """Session ended 5 minutes ago; grace has expired → order rejected (403)."""
    client = e2e
    order_service.clear_rate_limit()
    admin_h = _admin_headers(client)
    cpo     = _create_cpo(client, admin_h)
    link    = cpo["unique_link"]
    cpo_h   = _cpo_headers(client)
    pizza   = _add_pizza(client, cpo_h)

    now    = _utcnow()
    cpo_id = storage.load_config().cpos[0].id
    session = SessionFile(
        id=new_id(),
        cpo_id=cpo_id,
        team_name="Engineering",
        session_date=now.date(),
        start_time=(now - timedelta(hours=1)).strftime("%H:%M"),
        end_time=(now - timedelta(minutes=5)).strftime("%H:%M"),   # ended 5 min ago
        grace_period_minutes=2,
        created_at=datetime.now(tz=timezone.utc),
    )
    storage.save_session(session)

    r = client.post(
        f"/api/orders/{link}/submit",
        json={"items": [{"member_name": "Alice", "pizza_id": pizza["id"]}]},
    )
    assert r.status_code == 403, f"Expected 403 (past grace), got {r.status_code}"


# ---------------------------------------------------------------------------
# 6. One active session per CPO
# ---------------------------------------------------------------------------

def test_duplicate_session_rejected(e2e):
    client = e2e
    admin_h = _admin_headers(client)
    _create_cpo(client, admin_h)
    cpo_h = _cpo_headers(client)

    _create_active_session(client, cpo_h)

    # Second session must also have a future end_time (else 422 fires before 409).
    now = _utcnow()
    r = client.post(
        "/api/cpo/sessions",
        json={
            "session_date": now.date().isoformat(),
            "start_time": (now + timedelta(hours=1)).strftime("%H:%M"),
            "end_time":   (now + timedelta(hours=2)).strftime("%H:%M"),
        },
        headers=cpo_h,
    )
    assert r.status_code == 409


# ---------------------------------------------------------------------------
# 7. Unique pizza names per menu (case-insensitive)
# ---------------------------------------------------------------------------

def test_duplicate_pizza_name_rejected(e2e):
    client = e2e
    admin_h = _admin_headers(client)
    _create_cpo(client, admin_h)
    cpo_h = _cpo_headers(client)

    _add_pizza(client, cpo_h, "Margherita", 12.50)

    r = client.post("/api/cpo/menu", json={"name": "margherita", "price": 9.00}, headers=cpo_h)
    assert r.status_code == 409


# ---------------------------------------------------------------------------
# 8. Role restrictions
# ---------------------------------------------------------------------------

def test_admin_cannot_access_cpo_endpoints(e2e):
    client  = e2e
    admin_h = _admin_headers(client)
    assert client.get("/api/cpo/me",   headers=admin_h).status_code == 403
    assert client.get("/api/cpo/menu", headers=admin_h).status_code == 403


def test_cpo_cannot_access_admin_endpoints(e2e):
    client  = e2e
    admin_h = _admin_headers(client)
    _create_cpo(client, admin_h)
    cpo_h   = _cpo_headers(client)
    assert client.get("/api/admin/cpos", headers=cpo_h).status_code == 403


def test_team_link_unknown_returns_404(e2e):
    client = e2e
    r = client.get("/api/orders/doesnotexist1234567890")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# 9. Summary timing fields exposed for countdown
# ---------------------------------------------------------------------------

def test_status_response_includes_timing(e2e):
    client  = e2e
    admin_h = _admin_headers(client)
    cpo     = _create_cpo(client, admin_h)
    link    = cpo["unique_link"]
    cpo_h   = _cpo_headers(client)
    _add_pizza(client, cpo_h)
    _create_active_session(client, cpo_h)

    r = client.get(f"/api/orders/{link}")
    assert r.status_code == 200
    body = r.json()
    assert body["session_date"] is not None
    assert body["end_time"] is not None


# ---------------------------------------------------------------------------
# 10. SSE endpoint reachable with query-param token
# ---------------------------------------------------------------------------

def test_sse_accepts_token_query_param(e2e):
    client  = e2e
    admin_h = _admin_headers(client)
    _create_cpo(client, admin_h)
    cpo_h   = _cpo_headers(client)

    # Use a closed session so the stream terminates immediately
    cpo_id = storage.load_config().cpos[0].id
    session = SessionFile(
        id=new_id(),
        cpo_id=cpo_id,
        team_name="Engineering",
        session_date=date(2020, 1, 1),
        start_time="11:00",
        end_time="12:00",
        grace_period_minutes=2,
        created_at=datetime.now(tz=timezone.utc),
    )
    storage.save_session(session)

    sse_token_r = client.post(
        f"/api/cpo/sessions/{session.id}/sse-token",
        headers=cpo_h,
        json={},
    )
    assert sse_token_r.status_code == 201
    sse_token = sse_token_r.json()["sse_token"]

    r = client.get(f"/api/cpo/sessions/{session.id}/summary/sse?token={sse_token}")
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]
    assert "session_closed" in r.text


# ---------------------------------------------------------------------------
# Currency flows through to team order page
# ---------------------------------------------------------------------------

def test_currency_flows_to_order_page(e2e):
    """CPO sets a custom currency; team order page reflects it."""
    client = e2e
    admin_h = _admin_headers(client)
    cpo = _create_cpo(client, admin_h)
    unique_link = cpo["unique_link"]
    cpo_h = _cpo_headers(client)

    # Default is CHF
    r = client.get(f"/api/orders/{unique_link}")
    assert r.json()["currency"] == "CHF"

    # CPO updates currency
    r = client.patch("/api/cpo/currency", json={"currency": "EUR"}, headers=cpo_h)
    assert r.status_code == 200
    assert r.json()["currency"] == "EUR"

    # Team order page now reflects EUR
    r = client.get(f"/api/orders/{unique_link}")
    assert r.json()["currency"] == "EUR"

    # GET /api/cpo/me also reflects it
    r = client.get("/api/cpo/me", headers=cpo_h)
    assert r.json()["currency"] == "EUR"


# ---------------------------------------------------------------------------
# Team name rename flows through to public order page
# ---------------------------------------------------------------------------

def test_team_name_rename_flows_to_order_page(e2e):
    """CPO renames team; public order page immediately reflects the new name."""
    client = e2e
    admin_h = _admin_headers(client)
    cpo = _create_cpo(client, admin_h)
    unique_link = cpo["unique_link"]
    cpo_h = _cpo_headers(client)

    # Default name is set at creation
    r = client.get(f"/api/orders/{unique_link}")
    assert r.json()["team_name"] == cpo["team_name"]

    # CPO renames the team
    r = client.patch("/api/cpo/team-name", json={"team_name": "Pizza Squad"}, headers=cpo_h)
    assert r.status_code == 200
    assert r.json()["team_name"] == "Pizza Squad"

    # Public order page now shows the new name (reads live from CPO record)
    r = client.get(f"/api/orders/{unique_link}")
    assert r.json()["team_name"] == "Pizza Squad"


# ---------------------------------------------------------------------------
# Menu export / import roundtrip
# ---------------------------------------------------------------------------

def test_menu_export_import_roundtrip(e2e):
    """Export the menu, clear it, re-import — pizzas and URL are fully restored."""
    client = e2e
    admin_h = _admin_headers(client)
    _create_cpo(client, admin_h)
    cpo_h = _cpo_headers(client)

    # Build initial menu
    _add_pizza(client, cpo_h, "Margherita", 12.50)
    _add_pizza(client, cpo_h, "Pepperoni",  13.50)
    client.put("/api/cpo/menu/url", json={"pizzeria_url": "https://pizza.example.com"}, headers=cpo_h)

    # Export
    exported = client.get("/api/cpo/menu/export", headers=cpo_h).json()
    assert len(exported["dishes"]) == 2
    assert exported["url"] == "https://pizza.example.com"

    # Clear the menu by importing an empty list
    client.post("/api/cpo/menu/import", json={"dishes": []}, headers=cpo_h)
    assert client.get("/api/cpo/menu", headers=cpo_h).json() == []

    # Re-import the exported data
    r = client.post("/api/cpo/menu/import", json=exported, headers=cpo_h)
    assert r.status_code == 204

    # Verify full restoration
    menu = client.get("/api/cpo/menu", headers=cpo_h).json()
    assert {p["name"] for p in menu} == {"Margherita", "Pepperoni"}
    url = client.get("/api/cpo/menu/url", headers=cpo_h).json()["pizzeria_url"]
    assert url == "https://pizza.example.com"

    # Exported format must not expose internal IDs
    for p in exported["dishes"]:
        assert "id" not in p

