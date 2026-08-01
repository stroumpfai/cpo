"""
Tests for GET /api/admin/stats — per-team (CPO) usage statistics.
"""
from datetime import date, datetime, timedelta, timezone

import storage
from models import Order, SessionFile
from utils import new_id

# Fixtures from conftest.py: client, seeded_config, admin_headers, cpo_headers

_PAST = date(2020, 1, 1)


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc).replace(tzinfo=None)


def _save_session(
    team_id,
    *,
    session_date=_PAST,
    start_time="11:00",
    end_time="12:00",
    closed_at=None,
    created_at=None,
) -> SessionFile:
    session = SessionFile(
        id=new_id(),
        team_id=team_id,
        team_name="Engineering",
        session_date=session_date,
        start_time=start_time,
        end_time=end_time,
        grace_period_minutes=2,
        created_at=created_at or datetime.now(tz=timezone.utc),
        closed_at=closed_at,
    )
    storage.save_session(session)
    return session


def _add_orders(team_id, session_id, n):
    orders = [
        Order(
            id=new_id(),
            session_id=session_id,
            member_name=f"Member {i}",
            pizza_id="p1",
            pizza_name="Margherita",
            pizza_price=12.50,
            total_price=12.50,
            created_at=datetime.now(tz=timezone.utc),
            client_ip="127.0.0.1",
        )
        for i in range(n)
    ]
    storage.add_orders_to_session(team_id, session_id, orders)


def _entry_for(body, team_id):
    return next(e for e in body if e["team_id"] == team_id)


# ---------------------------------------------------------------------------
# GET /api/admin/stats
# ---------------------------------------------------------------------------

def test_stats_counts_only_closed_sessions(client, seeded_config, admin_headers):
    cpo_id = seeded_config["cpo_id"]

    closed1 = _save_session(cpo_id, session_date=_PAST)
    _add_orders(cpo_id, closed1.id, 2)
    closed2 = _save_session(cpo_id, session_date=date(2020, 2, 1))
    _add_orders(cpo_id, closed2.id, 1)

    active = _save_session(
        cpo_id, session_date=_utcnow().date(), start_time="00:00", end_time="23:59"
    )
    _add_orders(cpo_id, active.id, 1)

    upcoming = _save_session(
        cpo_id,
        session_date=(_utcnow().date() + timedelta(days=1)),
        start_time="00:00",
        end_time="23:59",
    )

    r = client.get("/api/admin/stats", headers=admin_headers)
    assert r.status_code == 200
    entry = _entry_for(r.json(), cpo_id)
    assert entry["past_session_count"] == 2
    assert entry["total_orders"] == 3
    latest_ids = {s["session_id"] for s in entry["latest_sessions"]}
    assert active.id not in latest_ids
    assert upcoming.id not in latest_ids


def test_stats_latest_three_newest_first(client, seeded_config, admin_headers):
    cpo_id = seeded_config["cpo_id"]
    sessions = []
    for i, day in enumerate([1, 2, 3, 4]):
        s = _save_session(cpo_id, session_date=date(2020, 1, day))
        _add_orders(cpo_id, s.id, i + 1)  # 1, 2, 3, 4 orders respectively
        sessions.append(s)

    r = client.get("/api/admin/stats", headers=admin_headers)
    entry = _entry_for(r.json(), cpo_id)

    assert entry["past_session_count"] == 4
    assert entry["total_orders"] == 1 + 2 + 3 + 4

    latest = entry["latest_sessions"]
    assert len(latest) == 3
    dates = [s["session_date"] for s in latest]
    assert dates == sorted(dates, reverse=True)
    # the oldest session (day 1, 1 order) must be excluded
    assert sessions[0].id not in {s["session_id"] for s in latest}
    # the newest (day 4, 4 orders) must be present with the right order_count
    newest = next(s for s in latest if s["session_id"] == sessions[3].id)
    assert newest["order_count"] == 4


def test_stats_force_closed_session_counts_as_past(client, seeded_config, admin_headers):
    cpo_id = seeded_config["cpo_id"]
    s = _save_session(
        cpo_id,
        session_date=_utcnow().date(),
        start_time="00:00",
        end_time="23:59",
        closed_at=datetime.now(tz=timezone.utc),
    )

    r = client.get("/api/admin/stats", headers=admin_headers)
    entry = _entry_for(r.json(), cpo_id)
    assert entry["past_session_count"] == 1
    assert entry["latest_sessions"][0]["session_id"] == s.id


def test_stats_zero_session_cpo(client, seeded_config, admin_headers):
    create = client.post(
        "/api/admin/cpos",
        json={
            "username": "alice",
            "email": "alice@example.com",
            "team_name": "Marketing",
            "initial_password": "securepass",
        },
        headers=admin_headers,
    )
    assert create.status_code == 201
    new_team_id = create.json()["team_id"]

    r = client.get("/api/admin/stats", headers=admin_headers)
    body = r.json()
    assert len(body) == 2

    entry = _entry_for(body, new_team_id)
    assert entry["past_session_count"] == 0
    assert entry["total_orders"] == 0
    assert entry["latest_sessions"] == []


def test_stats_requires_admin(client, seeded_config, cpo_headers):
    r = client.get("/api/admin/stats", headers=cpo_headers)
    assert r.status_code == 403


def test_stats_requires_auth(client, seeded_config):
    r = client.get("/api/admin/stats")
    assert r.status_code == 401
