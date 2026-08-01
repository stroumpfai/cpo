"""
Tests for GET /api/cpo/stats and POST /api/cpo/stats/reset.
"""
from datetime import date, datetime, timedelta, timezone

import storage
from models import Order, SessionFile
from utils import new_id

# Fixtures from conftest.py: client, seeded_config, seeded_menu, cpo_headers, admin_headers

_PAST = date(2020, 1, 1)


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc).replace(tzinfo=None)


def _save_session(
    cpo_id,
    *,
    session_date=_PAST,
    start_time="11:00",
    end_time="12:00",
    closed_at=None,
    created_at=None,
    menu_id=None,
) -> SessionFile:
    session = SessionFile(
        id=new_id(),
        team_id=cpo_id,
        team_name="Engineering",
        session_date=session_date,
        start_time=start_time,
        end_time=end_time,
        grace_period_minutes=2,
        created_at=created_at or datetime.now(tz=timezone.utc),
        closed_at=closed_at,
        menu_id=menu_id,
    )
    storage.save_session(session)
    return session


def _add_order(cpo_id, session_id, *, member_name="Alice", pizza_name="Margherita", quantity=1):
    order = Order(
        id=new_id(),
        session_id=session_id,
        member_name=member_name,
        pizza_id="p1",
        pizza_name=pizza_name,
        pizza_price=12.50,
        quantity=quantity,
        total_price=12.50 * quantity,
        created_at=datetime.now(tz=timezone.utc),
        client_ip="127.0.0.1",
    )
    storage.add_orders_to_session(cpo_id, session_id, [order])
    return order


# ---------------------------------------------------------------------------
# GET /api/cpo/stats
# ---------------------------------------------------------------------------

def test_stats_empty_cpo(client, seeded_config, seeded_menu, cpo_headers):
    r = client.get("/api/cpo/stats", headers=cpo_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["recent_sessions"] == []
    assert body["total_sessions"] == 0
    assert body["distinct_members"] == 0
    assert body["distinct_plates"] == 0
    assert body["stats_reset_at"] is None
    # the seeded default menu exists but has no orders yet
    assert len(body["menus"]) == 1
    assert body["menus"][0]["use_count"] == 0
    assert body["menus"][0]["top_plates"] == []
    assert body["menus"][0]["top_people"] == []


def test_stats_recent_sessions_last_five_most_recent_first(client, seeded_config, seeded_menu, cpo_headers):
    cpo_id = seeded_config["cpo_id"]
    menu_id = seeded_menu.id
    sessions = []
    for day in range(1, 7):   # 6 sessions, only the 5 most recent should be returned
        s = _save_session(cpo_id, session_date=date(2020, 1, day), menu_id=menu_id)
        _add_order(cpo_id, s.id, quantity=day)
        sessions.append(s)

    r = client.get("/api/cpo/stats", headers=cpo_headers)
    body = r.json()

    assert body["total_sessions"] == 6
    recent = body["recent_sessions"]
    assert len(recent) == 5
    dates = [row["session_date"] for row in recent]
    assert dates == sorted(dates, reverse=True)
    # the oldest session (day 1) must be excluded from the top-5
    assert sessions[0].id not in {row["session_id"] for row in recent}
    newest = next(row for row in recent if row["session_id"] == sessions[5].id)
    assert newest["item_count"] == 6
    assert newest["status"] == "closed"


def test_stats_menu_scoping(client, seeded_config, seeded_menu, cpo_headers):
    cpo_id = seeded_config["cpo_id"]
    menu_b = storage.create_menu(cpo_id, "Menu B")

    s_a = _save_session(cpo_id, menu_id=seeded_menu.id)
    _add_order(cpo_id, s_a.id, member_name="Alice", pizza_name="Margherita")
    _add_order(cpo_id, s_a.id, member_name="Alice", pizza_name="Margherita")

    s_b = _save_session(cpo_id, menu_id=menu_b.id)
    _add_order(cpo_id, s_b.id, member_name="Bob", pizza_name="Calzone")

    r = client.get("/api/cpo/stats", headers=cpo_headers)
    body = r.json()
    menus_by_id = {m["menu_id"]: m for m in body["menus"]}

    menu_a_stats = menus_by_id[seeded_menu.id]
    assert menu_a_stats["use_count"] == 1
    assert menu_a_stats["top_plates"] == [{"pizza_name": "Margherita", "count": 2}]
    assert menu_a_stats["top_people"] == [{"member_name": "Alice", "count": 2}]

    menu_b_stats = menus_by_id[menu_b.id]
    assert menu_b_stats["use_count"] == 1
    assert menu_b_stats["top_plates"] == [{"pizza_name": "Calzone", "count": 1}]
    assert menu_b_stats["top_people"] == [{"member_name": "Bob", "count": 1}]

    # general totals are not menu-scoped
    assert body["total_sessions"] == 2
    assert body["distinct_members"] == 2
    assert body["distinct_plates"] == 2


def test_stats_top3_capped_and_alphabetical_tiebreak(client, seeded_config, seeded_menu, cpo_headers):
    cpo_id = seeded_config["cpo_id"]
    s = _save_session(cpo_id, menu_id=seeded_menu.id)
    for name in ["Zeta", "Alpha", "Delta", "Beta"]:
        _add_order(cpo_id, s.id, member_name="Alice", pizza_name=name, quantity=1)

    r = client.get("/api/cpo/stats", headers=cpo_headers)
    menu_stats = next(m for m in r.json()["menus"] if m["menu_id"] == seeded_menu.id)
    plate_names = [row["pizza_name"] for row in menu_stats["top_plates"]]
    assert plate_names == ["Alpha", "Beta", "Delta"]   # tied at count=1, alphabetical, capped at 3


def test_stats_deleted_menu_orphaned_orders_counted_in_general_only(
    client, seeded_config, seeded_menu, cpo_headers
):
    cpo_id = seeded_config["cpo_id"]
    extra_menu = storage.create_menu(cpo_id, "Temporary menu")
    s = _save_session(cpo_id, menu_id=extra_menu.id)
    _add_order(cpo_id, s.id, member_name="Carol", pizza_name="Hawaiian")

    assert storage.delete_menu(cpo_id, extra_menu.id) is True

    r = client.get("/api/cpo/stats", headers=cpo_headers)
    body = r.json()
    # orphaned session/order still counted in general totals
    assert body["total_sessions"] == 1
    assert body["distinct_members"] == 1
    assert body["distinct_plates"] == 1
    # but there is no menu entry to attach the breakdown to
    assert body["menus"] == [] or all(m["menu_id"] != extra_menu.id for m in body["menus"])


def test_stats_use_count_counts_sessions_not_orders(client, seeded_config, seeded_menu, cpo_headers):
    cpo_id = seeded_config["cpo_id"]
    s1 = _save_session(cpo_id, menu_id=seeded_menu.id, session_date=date(2020, 1, 1))
    s2 = _save_session(cpo_id, menu_id=seeded_menu.id, session_date=date(2020, 1, 2))
    _add_order(cpo_id, s1.id, quantity=3)
    _add_order(cpo_id, s2.id, quantity=5)

    r = client.get("/api/cpo/stats", headers=cpo_headers)
    menu_stats = next(m for m in r.json()["menus"] if m["menu_id"] == seeded_menu.id)
    assert menu_stats["use_count"] == 2   # two sessions, not the 8 combined items


def test_stats_requires_cpo(client, seeded_config, admin_headers):
    r = client.get("/api/cpo/stats", headers=admin_headers)
    assert r.status_code == 403


def test_stats_requires_auth(client, seeded_config):
    r = client.get("/api/cpo/stats")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/cpo/stats/reset
# ---------------------------------------------------------------------------

def test_reset_stats_excludes_data_before_cutoff_keeps_it_after(client, seeded_config, seeded_menu, cpo_headers):
    cpo_id = seeded_config["cpo_id"]
    past_time = datetime.now(tz=timezone.utc) - timedelta(hours=2)
    s1 = _save_session(cpo_id, menu_id=seeded_menu.id, created_at=past_time)
    _add_order(cpo_id, s1.id)

    reset_resp = client.post("/api/cpo/stats/reset", headers=cpo_headers)
    assert reset_resp.status_code == 200
    reset_body = reset_resp.json()
    assert reset_body["stats_reset_at"] is not None
    assert reset_body["total_sessions"] == 0   # nothing created after the cutoff yet

    future_time = datetime.now(tz=timezone.utc) + timedelta(hours=2)
    s2 = _save_session(cpo_id, menu_id=seeded_menu.id, created_at=future_time)
    _add_order(cpo_id, s2.id)

    stats_after = client.get("/api/cpo/stats", headers=cpo_headers).json()
    assert stats_after["total_sessions"] == 1
    assert {row["session_id"] for row in stats_after["recent_sessions"]} == {s2.id}

    # session history is untouched by the reset — nothing was deleted
    all_sessions = client.get("/api/cpo/sessions", headers=cpo_headers).json()
    assert {s["id"] for s in all_sessions} == {s1.id, s2.id}


def test_reset_stats_requires_cpo(client, seeded_config, admin_headers):
    r = client.post("/api/cpo/stats/reset", headers=admin_headers)
    assert r.status_code == 403


def test_reset_stats_requires_auth(client, seeded_config):
    r = client.post("/api/cpo/stats/reset")
    assert r.status_code == 401
