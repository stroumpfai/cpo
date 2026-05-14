"""
Tests for the SSE summary endpoint (Phase 6):
  GET /api/cpo/sessions/{session_id}/summary/sse
"""
import asyncio
import json
from datetime import date, datetime, timezone

import pytest

import storage
from models import SessionFile
from services import cpo_service
from utils import new_id

# Fixtures from conftest.py: client, seeded_config, cpo_headers, tmp_storage


def _closed_session(seeded_config) -> SessionFile:
    session = SessionFile(
        id=new_id(),
        cpo_id=seeded_config["cpo_id"],
        team_name="Engineering",
        session_date=date(2020, 1, 1),
        start_time="11:00",
        end_time="12:00",
        grace_period_minutes=2,
        created_at=datetime.now(tz=timezone.utc),
    )
    storage.save_session(session)
    return session


def _upcoming_session(seeded_config) -> SessionFile:
    from datetime import timedelta
    future = date.today() + timedelta(days=365)
    session = SessionFile(
        id=new_id(),
        cpo_id=seeded_config["cpo_id"],
        team_name="Engineering",
        session_date=future,
        start_time="11:00",
        end_time="12:00",
        grace_period_minutes=2,
        created_at=datetime.now(tz=timezone.utc),
    )
    storage.save_session(session)
    return session


# ---------------------------------------------------------------------------
# Auth guards
# ---------------------------------------------------------------------------

def test_sse_requires_cpo_auth(client, seeded_config, admin_headers):
    session = _closed_session(seeded_config)
    r = client.get(f"/api/cpo/sessions/{session.id}/summary/sse", headers=admin_headers)
    assert r.status_code == 403


def test_sse_no_auth_rejected(client, seeded_config):
    session = _closed_session(seeded_config)
    r = client.get(f"/api/cpo/sessions/{session.id}/summary/sse")
    assert r.status_code == 401  # no header and no ?token= → 401


def test_sse_session_not_found(client, seeded_config, cpo_headers):
    r = client.get("/api/cpo/sessions/nonexistent/summary/sse", headers=cpo_headers)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Streaming content — closed session terminates cleanly
# ---------------------------------------------------------------------------

def test_sse_closed_session_emits_one_event_and_closes(client, seeded_config, cpo_headers):
    """
    A closed session should emit exactly one 'session_closed' event and then
    close the stream.  TestClient collects the full body since the stream ends.
    """
    session = _closed_session(seeded_config)
    r = client.get(
        f"/api/cpo/sessions/{session.id}/summary/sse",
        headers=cpo_headers,
    )
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]

    text = r.text
    assert "event: session_closed" in text
    assert "data:" in text


def test_sse_closed_session_data_is_valid_json(client, seeded_config, cpo_headers):
    session = _closed_session(seeded_config)
    r = client.get(f"/api/cpo/sessions/{session.id}/summary/sse", headers=cpo_headers)
    # Extract data line
    data_line = next(line for line in r.text.splitlines() if line.startswith("data:"))
    payload = json.loads(data_line[len("data:"):].strip())
    assert payload["session_id"] == session.id
    assert payload["status"] == "closed"
    assert "distribution" in payload
    assert "pizzeria" in payload


def test_sse_response_headers(client, seeded_config, cpo_headers):
    session = _closed_session(seeded_config)
    r = client.get(f"/api/cpo/sessions/{session.id}/summary/sse", headers=cpo_headers)
    assert r.headers.get("cache-control") == "no-cache"


# ---------------------------------------------------------------------------
# Async generator unit tests (no HTTP)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sse_generator_closed_session_terminates(seeded_config, tmp_storage):
    session = _closed_session(seeded_config)
    events = []
    async for chunk in cpo_service.session_sse_events(seeded_config["cpo_id"], session.id):
        events.append(chunk)

    assert len(events) == 1
    assert "session_closed" in events[0]


@pytest.mark.asyncio
async def test_sse_generator_missing_session(seeded_config, tmp_storage):
    events = []
    async for chunk in cpo_service.session_sse_events(seeded_config["cpo_id"], "ghost-id"):
        events.append(chunk)

    assert len(events) == 1
    assert "error" in events[0]


@pytest.mark.asyncio
async def test_sse_generator_upcoming_emits_update_then_stops_after_one_tick(seeded_config, tmp_storage, monkeypatch):
    """
    Patch asyncio.sleep to avoid waiting 1 s and cap the loop at 2 iterations.
    After the first emit (upcoming status) and the first sleep, we simulate the
    session becoming closed so the generator exits.
    """
    session = _upcoming_session(seeded_config)
    cpo_id = seeded_config["cpo_id"]

    sleep_count = 0

    async def fake_sleep(_):
        nonlocal sleep_count
        sleep_count += 1
        # After first sleep, overwrite the session with a closed one so generator exits
        closed = SessionFile(
            id=session.id,
            cpo_id=cpo_id,
            team_name="Engineering",
            session_date=date(2020, 1, 1),
            start_time="11:00",
            end_time="12:00",
            grace_period_minutes=2,
            created_at=session.created_at,
        )
        storage.save_session(closed)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    events = []
    async for chunk in cpo_service.session_sse_events(cpo_id, session.id):
        events.append(chunk)

    # First event: "update" (upcoming), second: "session_closed" (after fake_sleep rewrites session)
    assert any("update" in e for e in events)
    assert any("session_closed" in e for e in events)
    assert sleep_count == 1
