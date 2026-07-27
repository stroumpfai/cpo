import pytest
from datetime import date, datetime, timezone

import db
import schema
import storage
import utils
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from models import (
    AdminRecord,
    ConfigFile,
    CPORecord,
    Order,
    Pizza,
    SessionFile,
)


def _now():
    return datetime.now(timezone.utc)


@pytest.fixture(autouse=True)
def isolated_paths(tmp_storage):
    """Fresh SQLite database per test (see conftest.tmp_storage)."""
    return tmp_storage


def _seed_cpo(cpo_id="cpo-1"):
    """Insert a bare CPO row so sessions/menus for cpo_id satisfy foreign keys."""
    with db.get_engine().begin() as conn:
        conn.execute(
            sqlite_insert(schema.cpos)
            .values(
                id=cpo_id,
                username=f"user-{cpo_id}",
                email=f"{cpo_id}@example.com",
                password_hash="x",  # NOSONAR — test fixture, not a credential
                team_name="Engineering",
                unique_link=utils.generate_link(),
                created_at="2026-01-01T00:00:00Z",
            )
            .on_conflict_do_nothing()
        )


def _make_config(tmp_path) -> ConfigFile:
    admin = AdminRecord(
        id=1,
        username="admin",
        password_hash=utils.hash_password("secret"),
        created_at=_now(),
    )
    cpo = CPORecord(
        id=utils.new_id(),
        username="john",
        email="john@example.com",
        password_hash=utils.hash_password("pass1234"),
        team_name="Engineering",
        unique_link=utils.generate_link(),
        created_at=_now(),
    )
    return ConfigFile(admins=[admin], cpos=[cpo])


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def test_save_and_load_config(tmp_path):
    cfg = _make_config(tmp_path)
    storage.save_config(cfg)
    loaded = storage.load_config()
    assert [a.username for a in loaded.admins] == ["admin"]
    assert len(loaded.cpos) == 1
    assert loaded.cpos[0].username == "john"


def test_config_missing_raises():
    with pytest.raises(FileNotFoundError):
        storage.load_config()


def test_save_config_twice_upserts(tmp_path):
    cfg = _make_config(tmp_path)
    storage.save_config(cfg)
    cfg.admins[0].username = "root"
    cfg.cpos[0].team_name = "Design"
    storage.save_config(cfg)
    loaded = storage.load_config()
    assert loaded.admins[0].username == "root"
    assert len(loaded.cpos) == 1
    assert loaded.cpos[0].team_name == "Design"


def test_save_config_removed_cpo_cascades(tmp_path):
    cfg = _make_config(tmp_path)
    storage.save_config(cfg)
    cpo_id = cfg.cpos[0].id
    s = _make_session(cpo_id)
    storage.save_session(s)
    menu = storage.create_menu(cpo_id, "Default")
    menu.pizzas = [Pizza(id="p1", name="M", price=10.0)]
    storage.save_menu(menu)

    storage.save_config(ConfigFile(admins=cfg.admins, cpos=[]))

    assert storage.load_config().cpos == []
    assert storage.load_session(cpo_id, s.id) is None
    assert storage.list_menus(cpo_id) == []


# ---------------------------------------------------------------------------
# Menus
# ---------------------------------------------------------------------------

def test_no_menus_initially(tmp_path):
    assert storage.list_menus("cpo-1") == []
    assert storage.get_default_menu("cpo-1") is None


def test_create_first_menu_is_default(tmp_path):
    _seed_cpo()
    menu = storage.create_menu("cpo-1", "Pizzas")
    assert menu.is_default is True
    assert menu.name == "Pizzas"
    assert storage.get_default_menu("cpo-1").id == menu.id


def test_second_menu_not_default(tmp_path):
    _seed_cpo()
    first = storage.create_menu("cpo-1", "Pizzas")
    second = storage.create_menu("cpo-1", "Thai")
    assert second.is_default is False
    assert storage.get_default_menu("cpo-1").id == first.id


def test_save_and_load_menu(tmp_path):
    _seed_cpo()
    menu = storage.create_menu("cpo-1", "Pizzas", pizzeria_url="https://p.example.com")
    menu.pizzas = [Pizza(id="p1", name="Margherita", price=12.50)]
    storage.save_menu(menu)
    loaded = storage.get_menu("cpo-1", menu.id)
    assert len(loaded.pizzas) == 1
    assert loaded.pizzas[0].name == "Margherita"
    assert loaded.pizzeria_url == "https://p.example.com"
    assert loaded.name == "Pizzas"


def test_save_menu_updates_name_and_url(tmp_path):
    _seed_cpo()
    menu = storage.create_menu("cpo-1", "Pizzas")
    menu.name = "Italian"
    menu.pizzeria_url = "https://new.example.com"
    storage.save_menu(menu)
    loaded = storage.get_menu("cpo-1", menu.id)
    assert loaded.name == "Italian"
    assert loaded.pizzeria_url == "https://new.example.com"


def test_save_menu_missing_raises(tmp_path):
    _seed_cpo()
    menu = storage.create_menu("cpo-1", "Pizzas")
    storage.delete_menu("cpo-1", menu.id)
    with pytest.raises(ValueError):
        storage.save_menu(menu)


def test_save_menu_never_touches_default_flag(tmp_path):
    """A stale Menu object cannot flip is_default and break the unique index."""
    _seed_cpo()
    first = storage.create_menu("cpo-1", "Pizzas")
    second = storage.create_menu("cpo-1", "Thai")
    second.is_default = True   # stale/tampered in-memory state
    storage.save_menu(second)
    assert storage.get_default_menu("cpo-1").id == first.id


def test_get_menu_scoped_to_cpo(tmp_path):
    _seed_cpo("cpo-1")
    _seed_cpo("cpo-2")
    menu = storage.create_menu("cpo-1", "Pizzas")
    assert storage.get_menu("cpo-2", menu.id) is None


def test_list_menus_creation_order(tmp_path):
    _seed_cpo()
    storage.create_menu("cpo-1", "Pizzas")
    storage.create_menu("cpo-1", "Thai")
    storage.create_menu("cpo-1", "Burgers")
    assert [m.name for m in storage.list_menus("cpo-1")] == ["Pizzas", "Thai", "Burgers"]


def test_set_default_menu_swaps(tmp_path):
    _seed_cpo()
    storage.create_menu("cpo-1", "Pizzas")
    second = storage.create_menu("cpo-1", "Thai")
    assert storage.set_default_menu("cpo-1", second.id) is True
    menus = {m.name: m.is_default for m in storage.list_menus("cpo-1")}
    assert menus == {"Pizzas": False, "Thai": True}


def test_set_default_menu_unknown_returns_false(tmp_path):
    _seed_cpo()
    storage.create_menu("cpo-1", "Pizzas")
    assert storage.set_default_menu("cpo-1", "nope") is False
    assert storage.get_default_menu("cpo-1").name == "Pizzas"


def test_delete_menu_cascades_pizzas(tmp_path):
    _seed_cpo()
    menu = storage.create_menu("cpo-1", "Pizzas")
    menu.pizzas = [Pizza(id="p1", name="Margherita", price=12.50)]
    storage.save_menu(menu)
    assert storage.delete_menu("cpo-1", menu.id) is True
    assert storage.list_menus("cpo-1") == []
    with db.get_engine().begin() as conn:
        from sqlalchemy import func, select
        count = conn.execute(select(func.count()).select_from(schema.pizzas)).scalar()
    assert count == 0


def test_delete_default_menu_promotes_oldest_remaining(tmp_path):
    _seed_cpo()
    first = storage.create_menu("cpo-1", "Pizzas")
    storage.create_menu("cpo-1", "Thai")
    storage.create_menu("cpo-1", "Burgers")
    storage.delete_menu("cpo-1", first.id)
    menus = storage.list_menus("cpo-1")
    assert [m.name for m in menus] == ["Thai", "Burgers"]
    assert [m.is_default for m in menus] == [True, False]


def test_delete_menu_nulls_session_reference(tmp_path):
    _seed_cpo()
    menu = storage.create_menu("cpo-1", "Pizzas")
    s = _make_session()
    s.menu_id = menu.id
    storage.save_session(s)
    storage.delete_menu("cpo-1", menu.id)
    assert storage.load_session("cpo-1", s.id).menu_id is None


def test_delete_menu_unknown_returns_false(tmp_path):
    _seed_cpo()
    assert storage.delete_menu("cpo-1", "nope") is False


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

def _make_session(cpo_id="cpo-1") -> SessionFile:
    _seed_cpo(cpo_id)  # sessions reference cpos; ensure the row exists
    return SessionFile(
        id=utils.new_id(),
        cpo_id=cpo_id,
        team_name="Engineering",
        session_date=date(2026, 5, 14),
        start_time="11:30",
        end_time="12:00",
        created_at=_now(),
    )


def test_save_and_load_session(tmp_path):
    s = _make_session()
    storage.save_session(s)
    loaded = storage.load_session(s.cpo_id, s.id)
    assert loaded is not None
    assert loaded.id == s.id
    assert loaded.orders == []


def test_load_session_missing_returns_none():
    assert storage.load_session("cpo-1", "nonexistent") is None


def test_list_sessions_empty():
    assert storage.list_sessions("cpo-1") == []


def test_list_sessions_scoped_to_cpo(tmp_path):
    s1 = _make_session("cpo-1")
    storage.save_session(s1)
    s2 = _make_session("cpo-2")
    storage.save_session(s2)
    storage.create_menu(s1.cpo_id, "Default")
    sessions = storage.list_sessions(s1.cpo_id)
    assert [s.id for s in sessions] == [s1.id]


def test_session_roundtrip_preserves_menu_id(tmp_path):
    s = _make_session()
    menu = storage.create_menu(s.cpo_id, "Pizzas")
    s.menu_id = menu.id
    storage.save_session(s)
    assert storage.load_session(s.cpo_id, s.id).menu_id == menu.id


def test_save_session_preserves_concurrent_orders(tmp_path):
    """A stale save_session (e.g. close_session) must not drop orders added in between."""
    s = _make_session()
    storage.save_session(s)
    stale = s.model_copy(deep=True)

    storage.add_order_to_session(s.cpo_id, s.id, _make_order(s.id))

    stale.closed_at = _now()
    storage.save_session(stale)

    loaded = storage.load_session(s.cpo_id, s.id)
    assert loaded.closed_at is not None
    assert len(loaded.orders) == 1


# ---------------------------------------------------------------------------
# Orders inside sessions
# ---------------------------------------------------------------------------

def _make_order(session_id: str) -> Order:
    return Order(
        id=utils.new_id(),
        session_id=session_id,
        member_name="Alice",
        pizza_id="p1",
        pizza_name="Margherita",
        pizza_price=12.50,
        total_price=12.50,
        created_at=_now(),
        client_ip="127.0.0.1",
    )


def test_add_order(tmp_path):
    s = _make_session()
    storage.save_session(s)
    order = _make_order(s.id)
    storage.add_order_to_session(s.cpo_id, s.id, order)
    loaded = storage.load_session(s.cpo_id, s.id)
    assert len(loaded.orders) == 1
    assert loaded.orders[0].member_name == "Alice"


# ---------------------------------------------------------------------------
# Session usage stats
# ---------------------------------------------------------------------------

def test_list_session_stats_counts_orders(tmp_path):
    s1 = _make_session("cpo-1")
    storage.save_session(s1)
    storage.add_order_to_session(s1.cpo_id, s1.id, _make_order(s1.id))
    storage.add_order_to_session(s1.cpo_id, s1.id, _make_order(s1.id))

    s2 = _make_session("cpo-1")
    storage.save_session(s2)

    rows = {r.id: r for r in storage.list_session_stats()}
    assert rows[s1.id].order_count == 2
    assert rows[s2.id].order_count == 0
    # fields needed by compute_session_status must be present
    assert rows[s1.id].session_date == s1.session_date
    assert rows[s1.id].start_time == s1.start_time
    assert rows[s1.id].end_time == s1.end_time
    assert rows[s1.id].grace_period_minutes == s1.grace_period_minutes
    assert rows[s1.id].closed_at is None


def test_delete_order(tmp_path):
    s = _make_session()
    storage.save_session(s)
    o = _make_order(s.id)
    storage.add_order_to_session(s.cpo_id, s.id, o)
    result = storage.delete_order_from_session(s.cpo_id, s.id, o.id)
    assert result is True
    loaded = storage.load_session(s.cpo_id, s.id)
    assert loaded.orders == []


def test_delete_nonexistent_order(tmp_path):
    s = _make_session()
    storage.save_session(s)
    result = storage.delete_order_from_session(s.cpo_id, s.id, "bad-id")
    assert result is False


def test_set_order_received_true(tmp_path):
    s = _make_session()
    storage.save_session(s)
    o = _make_order(s.id)
    storage.add_order_to_session(s.cpo_id, s.id, o)

    result = storage.set_order_received(s.cpo_id, s.id, o.id, True)

    assert result is True
    loaded = storage.load_session(s.cpo_id, s.id)
    assert loaded.orders[0].received is True


def test_set_order_received_false(tmp_path):
    s = _make_session()
    storage.save_session(s)
    o = _make_order(s.id)
    storage.add_order_to_session(s.cpo_id, s.id, o)
    storage.set_order_received(s.cpo_id, s.id, o.id, True)

    result = storage.set_order_received(s.cpo_id, s.id, o.id, False)

    assert result is True
    loaded = storage.load_session(s.cpo_id, s.id)
    assert loaded.orders[0].received is False


def test_set_order_received_nonexistent_order(tmp_path):
    s = _make_session()
    storage.save_session(s)
    result = storage.set_order_received(s.cpo_id, s.id, "bad-id", True)
    assert result is False


def test_set_order_received_nonexistent_session(tmp_path):
    s = _make_session()
    storage.save_session(s)
    result = storage.set_order_received(s.cpo_id, "no-such-session", "any-id", True)
    assert result is False


def test_order_mutations_wrong_cpo_return_false(tmp_path):
    s = _make_session()
    storage.save_session(s)
    o = _make_order(s.id)
    storage.add_order_to_session(s.cpo_id, s.id, o)
    assert storage.set_order_received("other-cpo", s.id, o.id, True) is False
    assert storage.delete_order_from_session("other-cpo", s.id, o.id) is False
    assert len(storage.load_session(s.cpo_id, s.id).orders) == 1


# ---------------------------------------------------------------------------
# Order mutations scoped to a CPO (no session_id needed) — used by the
# dashboard's delete/mark-received actions, which only know the order_id.
# ---------------------------------------------------------------------------

def test_delete_order_for_cpo_finds_it_without_session_id(tmp_path):
    # Two sessions for the same CPO; the order lives in the second one.
    s1 = _make_session()
    storage.save_session(s1)
    s2 = _make_session(s1.cpo_id)
    storage.save_session(s2)
    o = _make_order(s2.id)
    storage.add_order_to_session(s2.cpo_id, s2.id, o)

    assert storage.delete_order_for_cpo(s1.cpo_id, o.id) is True
    assert storage.load_session(s2.cpo_id, s2.id).orders == []


def test_delete_order_for_cpo_nonexistent_returns_false(tmp_path):
    s = _make_session()
    storage.save_session(s)
    assert storage.delete_order_for_cpo(s.cpo_id, "bad-id") is False


def test_delete_order_for_cpo_wrong_cpo_returns_false(tmp_path):
    s = _make_session()
    storage.save_session(s)
    o = _make_order(s.id)
    storage.add_order_to_session(s.cpo_id, s.id, o)
    assert storage.delete_order_for_cpo("other-cpo", o.id) is False
    assert len(storage.load_session(s.cpo_id, s.id).orders) == 1


def test_set_order_received_for_cpo_finds_it_without_session_id(tmp_path):
    s1 = _make_session()
    storage.save_session(s1)
    s2 = _make_session(s1.cpo_id)
    storage.save_session(s2)
    o = _make_order(s2.id)
    storage.add_order_to_session(s2.cpo_id, s2.id, o)

    assert storage.set_order_received_for_cpo(s1.cpo_id, o.id, True) is True
    assert storage.load_session(s2.cpo_id, s2.id).orders[0].received is True


def test_set_order_received_for_cpo_nonexistent_returns_false(tmp_path):
    s = _make_session()
    storage.save_session(s)
    assert storage.set_order_received_for_cpo(s.cpo_id, "bad-id", True) is False


def test_set_order_received_for_cpo_wrong_cpo_returns_false(tmp_path):
    s = _make_session()
    storage.save_session(s)
    o = _make_order(s.id)
    storage.add_order_to_session(s.cpo_id, s.id, o)
    assert storage.set_order_received_for_cpo("other-cpo", o.id, True) is False


def test_order_received_defaults_false(tmp_path):
    s = _make_session()
    storage.save_session(s)
    o = _make_order(s.id)
    storage.add_order_to_session(s.cpo_id, s.id, o)
    loaded = storage.load_session(s.cpo_id, s.id)
    assert loaded.orders[0].received is False


# ---------------------------------------------------------------------------
# utils — session status
# ---------------------------------------------------------------------------

from utils import compute_session_status
from unittest.mock import patch


def test_status_upcoming():
    with patch("utils.now_utc", return_value=datetime(2026, 5, 14, 10, 0)):
        assert compute_session_status(date(2026, 5, 14), "11:30", "12:00") == "upcoming"


def test_status_active():
    with patch("utils.now_utc", return_value=datetime(2026, 5, 14, 11, 45)):
        assert compute_session_status(date(2026, 5, 14), "11:30", "12:00") == "active"


def test_status_in_grace_period():
    with patch("utils.now_utc", return_value=datetime(2026, 5, 14, 12, 1)):
        assert compute_session_status(date(2026, 5, 14), "11:30", "12:00") == "active"


def test_status_closed():
    with patch("utils.now_utc", return_value=datetime(2026, 5, 14, 12, 3)):
        assert compute_session_status(date(2026, 5, 14), "11:30", "12:00") == "closed"


# ---------------------------------------------------------------------------
# utils — passwords and link generation
# ---------------------------------------------------------------------------

def test_password_hash_and_verify():
    h = utils.hash_password("mysecret")
    assert utils.verify_password("mysecret", h)
    assert not utils.verify_password("wrong", h)


def test_generate_link_length():
    link = utils.generate_link()
    assert len(link) >= 16
    assert link.isalnum()
