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
    TeamRecord,
)


def _now():
    return datetime.now(timezone.utc)


@pytest.fixture(autouse=True)
def isolated_paths(tmp_storage):
    """Fresh SQLite database per test (see conftest.tmp_storage)."""
    return tmp_storage


def _seed_cpo(team_id="cpo-1"):
    """Insert a bare team row so sessions/menus for team_id satisfy the FK.

    Menus/sessions now reference teams.id (not cpos.id) — see schema.py.
    """
    with db.get_engine().begin() as conn:
        conn.execute(
            sqlite_insert(schema.teams)
            .values(
                id=team_id,
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
    # Team and CPO login share one id, like the Alembic migration does for
    # pre-existing single-CPO teams — keeps this fixture simple.
    shared_id = utils.new_id()
    team = TeamRecord(
        id=shared_id,
        team_name="Engineering",
        unique_link=utils.generate_link(),
        created_at=_now(),
    )
    cpo = CPORecord(
        id=shared_id,
        team_id=shared_id,
        username="john",
        email="john@example.com",
        password_hash=utils.hash_password("pass1234"),
        created_at=_now(),
    )
    return ConfigFile(admins=[admin], cpos=[cpo], teams=[team])


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
    assert len(loaded.teams) == 1
    assert loaded.teams[0].team_name == "Engineering"


def test_config_missing_raises():
    with pytest.raises(FileNotFoundError):
        storage.load_config()


def test_save_config_twice_upserts(tmp_path):
    cfg = _make_config(tmp_path)
    storage.save_config(cfg)
    cfg.admins[0].username = "root"
    cfg.teams[0].team_name = "Design"
    storage.save_config(cfg)
    loaded = storage.load_config()
    assert loaded.admins[0].username == "root"
    assert len(loaded.cpos) == 1
    assert loaded.teams[0].team_name == "Design"


def test_save_config_removed_cpo_cascades(tmp_path):
    """Removing a team from cfg.teams cascades its logins, menus, sessions."""
    cfg = _make_config(tmp_path)
    storage.save_config(cfg)
    team_id = cfg.teams[0].id
    s = _make_session(team_id)
    storage.save_session(s)
    menu = storage.create_menu(team_id, "Default")
    menu.pizzas = [Pizza(id="p1", name="M", price=10.0)]
    storage.save_menu(menu)

    storage.save_config(ConfigFile(admins=cfg.admins, cpos=[], teams=[]))

    assert storage.load_config().cpos == []
    assert storage.load_config().teams == []
    assert storage.load_session(team_id, s.id) is None
    assert storage.list_menus(team_id) == []


def test_update_team_fields_rejects_unknown_column(tmp_path):
    cfg = _make_config(tmp_path)
    storage.save_config(cfg)
    with pytest.raises(ValueError):
        storage.update_team_fields(cfg.teams[0].id, username="nope")


def test_update_team_fields_updates_and_returns_record(tmp_path):
    cfg = _make_config(tmp_path)
    storage.save_config(cfg)
    updated = storage.update_team_fields(cfg.teams[0].id, currency="EUR")
    assert updated.currency == "EUR"
    assert storage.load_config().teams[0].currency == "EUR"


def test_update_team_fields_unknown_team_returns_none(tmp_path):
    assert storage.update_team_fields("nope", currency="EUR") is None


# ---------------------------------------------------------------------------
# Per-login language preference
# ---------------------------------------------------------------------------

def test_update_cpo_fields_sets_language(tmp_path):
    cfg = _make_config(tmp_path)
    storage.save_config(cfg)
    updated = storage.update_cpo_fields(cfg.cpos[0].id, language="de-CH")
    assert updated.language == "de-CH"
    assert storage.load_config().cpos[0].language == "de-CH"


def test_update_cpo_fields_clears_language(tmp_path):
    cfg = _make_config(tmp_path)
    storage.save_config(cfg)
    storage.update_cpo_fields(cfg.cpos[0].id, language="fr-CH")
    assert storage.update_cpo_fields(cfg.cpos[0].id, language=None).language is None


def test_update_cpo_fields_rejects_unknown_column(tmp_path):
    cfg = _make_config(tmp_path)
    storage.save_config(cfg)
    with pytest.raises(ValueError):
        storage.update_cpo_fields(cfg.cpos[0].id, nope="x")


def test_update_cpo_fields_unknown_cpo_returns_none(tmp_path):
    assert storage.update_cpo_fields("nope", language="en") is None


def test_update_cpo_fields_leaves_other_columns_alone(tmp_path):
    cfg = _make_config(tmp_path)
    storage.save_config(cfg)
    storage.update_cpo_fields(cfg.cpos[0].id, language="it-CH")
    loaded = storage.load_config().cpos[0]
    assert loaded.username == "john"
    assert loaded.email == "john@example.com"


def test_update_admin_fields_sets_language(tmp_path):
    cfg = _make_config(tmp_path)
    storage.save_config(cfg)
    updated = storage.update_admin_fields(1, language="fr-CH")
    assert updated.language == "fr-CH"
    assert storage.load_config().admins[0].language == "fr-CH"


def test_update_admin_fields_unknown_admin_returns_none(tmp_path):
    assert storage.update_admin_fields(999, language="en") is None


def test_rows_written_before_the_language_column_load_as_none(tmp_path):
    """Migration 0007 adds the column nullable with no backfill, so every
    pre-existing account reads back as "no explicit choice"."""
    cfg = _make_config(tmp_path)
    storage.save_config(cfg)
    # Rewrite both login rows the way a pre-0007 build would have: no language.
    with db.get_engine().begin() as conn:
        conn.execute(schema.cpos.update().values(language=None))
        conn.execute(schema.admins.update().values(language=None))
    loaded = storage.load_config()
    assert loaded.cpos[0].language is None
    assert loaded.admins[0].language is None


def test_unsupported_stored_language_loads_as_none(tmp_path):
    """A tag this build no longer supports must not break the whole config load."""
    cfg = _make_config(tmp_path)
    storage.save_config(cfg)
    with db.get_engine().begin() as conn:
        conn.execute(schema.cpos.update().values(language="de-DE"))
    assert storage.load_config().cpos[0].language is None


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
    """Cross-TEAM isolation: a menu created for one team is invisible to another."""
    _seed_cpo("cpo-1")
    _seed_cpo("cpo-2")
    menu = storage.create_menu("cpo-1", "Pizzas")
    assert storage.get_menu("cpo-2", menu.id) is None


def test_get_menu_visible_to_same_team(tmp_path):
    """Same-team sharing: any login scoped by the SAME team_id sees the menu —
    storage has no concept of "login", only team_id, so two different CPO
    logins on one team naturally see the same menus."""
    _seed_cpo("shared-team")
    menu = storage.create_menu("shared-team", "Pizzas")
    # Simulate a second login on the same team: it scopes storage calls with
    # the identical team_id, so it sees (and can mutate) the same menu.
    loaded = storage.get_menu("shared-team", menu.id)
    assert loaded is not None
    assert loaded.id == menu.id


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

def _make_session(team_id="cpo-1") -> SessionFile:
    _seed_cpo(team_id)  # sessions reference teams; ensure the row exists
    return SessionFile(
        id=utils.new_id(),
        team_id=team_id,
        team_name="Engineering",
        session_date=date(2026, 5, 14),
        start_time="11:30",
        end_time="12:00",
        created_at=_now(),
    )


def test_save_and_load_session(tmp_path):
    s = _make_session()
    storage.save_session(s)
    loaded = storage.load_session(s.team_id, s.id)
    assert loaded is not None
    assert loaded.id == s.id
    assert loaded.orders == []


def test_load_session_missing_returns_none():
    assert storage.load_session("cpo-1", "nonexistent") is None


def test_list_sessions_empty():
    assert storage.list_sessions("cpo-1") == []


def test_list_sessions_scoped_to_cpo(tmp_path):
    """Cross-TEAM isolation: sessions of one team are invisible to another."""
    s1 = _make_session("cpo-1")
    storage.save_session(s1)
    s2 = _make_session("cpo-2")
    storage.save_session(s2)
    storage.create_menu(s1.team_id, "Default")
    sessions = storage.list_sessions(s1.team_id)
    assert [s.id for s in sessions] == [s1.id]


def test_list_sessions_visible_to_same_team(tmp_path):
    """Same-team sharing: sessions are scoped by team_id only, so a second
    login on the same team sees the same sessions."""
    s1 = _make_session("shared-team")
    storage.save_session(s1)
    sessions = storage.list_sessions("shared-team")
    assert [s.id for s in sessions] == [s1.id]


def test_session_roundtrip_preserves_menu_id(tmp_path):
    s = _make_session()
    menu = storage.create_menu(s.team_id, "Pizzas")
    s.menu_id = menu.id
    storage.save_session(s)
    assert storage.load_session(s.team_id, s.id).menu_id == menu.id


def test_save_session_preserves_concurrent_orders(tmp_path):
    """A stale save_session (e.g. close_session) must not drop orders added in between."""
    s = _make_session()
    storage.save_session(s)
    stale = s.model_copy(deep=True)

    storage.add_order_to_session(s.team_id, s.id, _make_order(s.id))

    stale.closed_at = _now()
    storage.save_session(stale)

    loaded = storage.load_session(s.team_id, s.id)
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
    storage.add_order_to_session(s.team_id, s.id, order)
    loaded = storage.load_session(s.team_id, s.id)
    assert len(loaded.orders) == 1
    assert loaded.orders[0].member_name == "Alice"


# ---------------------------------------------------------------------------
# Session usage stats
# ---------------------------------------------------------------------------

def test_list_session_stats_counts_orders(tmp_path):
    s1 = _make_session("cpo-1")
    storage.save_session(s1)
    storage.add_order_to_session(s1.team_id, s1.id, _make_order(s1.id))
    storage.add_order_to_session(s1.team_id, s1.id, _make_order(s1.id))

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
    storage.add_order_to_session(s.team_id, s.id, o)
    result = storage.delete_order_from_session(s.team_id, s.id, o.id)
    assert result is True
    loaded = storage.load_session(s.team_id, s.id)
    assert loaded.orders == []


def test_delete_nonexistent_order(tmp_path):
    s = _make_session()
    storage.save_session(s)
    result = storage.delete_order_from_session(s.team_id, s.id, "bad-id")
    assert result is False


def test_set_order_received_true(tmp_path):
    s = _make_session()
    storage.save_session(s)
    o = _make_order(s.id)
    storage.add_order_to_session(s.team_id, s.id, o)

    result = storage.set_order_received(s.team_id, s.id, o.id, True)

    assert result is True
    loaded = storage.load_session(s.team_id, s.id)
    assert loaded.orders[0].received is True


def test_set_order_received_false(tmp_path):
    s = _make_session()
    storage.save_session(s)
    o = _make_order(s.id)
    storage.add_order_to_session(s.team_id, s.id, o)
    storage.set_order_received(s.team_id, s.id, o.id, True)

    result = storage.set_order_received(s.team_id, s.id, o.id, False)

    assert result is True
    loaded = storage.load_session(s.team_id, s.id)
    assert loaded.orders[0].received is False


def test_set_order_received_nonexistent_order(tmp_path):
    s = _make_session()
    storage.save_session(s)
    result = storage.set_order_received(s.team_id, s.id, "bad-id", True)
    assert result is False


def test_set_order_received_nonexistent_session(tmp_path):
    s = _make_session()
    storage.save_session(s)
    result = storage.set_order_received(s.team_id, "no-such-session", "any-id", True)
    assert result is False


def test_order_mutations_wrong_cpo_return_false(tmp_path):
    s = _make_session()
    storage.save_session(s)
    o = _make_order(s.id)
    storage.add_order_to_session(s.team_id, s.id, o)
    assert storage.set_order_received("other-cpo", s.id, o.id, True) is False
    assert storage.delete_order_from_session("other-cpo", s.id, o.id) is False
    assert len(storage.load_session(s.team_id, s.id).orders) == 1


# ---------------------------------------------------------------------------
# Order mutations scoped to a team (no session_id needed) — used by the
# dashboard's delete/mark-received actions, which only know the order_id.
# ---------------------------------------------------------------------------

def test_delete_order_for_cpo_finds_it_without_session_id(tmp_path):
    # Two sessions for the same team; the order lives in the second one.
    s1 = _make_session()
    storage.save_session(s1)
    s2 = _make_session(s1.team_id)
    storage.save_session(s2)
    o = _make_order(s2.id)
    storage.add_order_to_session(s2.team_id, s2.id, o)

    assert storage.delete_order_for_cpo(s1.team_id, o.id) is True
    assert storage.load_session(s2.team_id, s2.id).orders == []


def test_delete_order_for_cpo_nonexistent_returns_false(tmp_path):
    s = _make_session()
    storage.save_session(s)
    assert storage.delete_order_for_cpo(s.team_id, "bad-id") is False


def test_delete_order_for_cpo_wrong_cpo_returns_false(tmp_path):
    s = _make_session()
    storage.save_session(s)
    o = _make_order(s.id)
    storage.add_order_to_session(s.team_id, s.id, o)
    assert storage.delete_order_for_cpo("other-cpo", o.id) is False
    assert len(storage.load_session(s.team_id, s.id).orders) == 1


def test_set_order_received_for_cpo_finds_it_without_session_id(tmp_path):
    s1 = _make_session()
    storage.save_session(s1)
    s2 = _make_session(s1.team_id)
    storage.save_session(s2)
    o = _make_order(s2.id)
    storage.add_order_to_session(s2.team_id, s2.id, o)

    assert storage.set_order_received_for_cpo(s1.team_id, o.id, True) is True
    assert storage.load_session(s2.team_id, s2.id).orders[0].received is True


def test_set_order_received_for_cpo_nonexistent_returns_false(tmp_path):
    s = _make_session()
    storage.save_session(s)
    assert storage.set_order_received_for_cpo(s.team_id, "bad-id", True) is False


def test_set_order_received_for_cpo_wrong_cpo_returns_false(tmp_path):
    s = _make_session()
    storage.save_session(s)
    o = _make_order(s.id)
    storage.add_order_to_session(s.team_id, s.id, o)
    assert storage.set_order_received_for_cpo("other-cpo", o.id, True) is False


def test_order_received_defaults_false(tmp_path):
    s = _make_session()
    storage.save_session(s)
    o = _make_order(s.id)
    storage.add_order_to_session(s.team_id, s.id, o)
    loaded = storage.load_session(s.team_id, s.id)
    assert loaded.orders[0].received is False


# ---------------------------------------------------------------------------
# Team invites
# ---------------------------------------------------------------------------

from models import TeamInvite


def test_create_and_get_invite(tmp_path):
    cfg = _make_config(tmp_path)
    storage.save_config(cfg)
    team_id = cfg.teams[0].id
    invite = TeamInvite(
        id=utils.new_id(),
        team_id=team_id,
        token=utils.generate_link(),
        created_by_cpo_id=cfg.cpos[0].id,
        created_at=_now(),
        expires_at=_now(),
    )
    storage.create_invite(invite)
    loaded = storage.get_invite_by_token(invite.token)
    assert loaded is not None
    assert loaded.id == invite.id
    assert loaded.used_at is None


def test_get_invite_by_token_unknown_returns_none(tmp_path):
    assert storage.get_invite_by_token("nope") is None


def test_list_invites_scoped_to_team(tmp_path):
    cfg = _make_config(tmp_path)
    storage.save_config(cfg)
    team_id = cfg.teams[0].id
    invite = TeamInvite(
        id=utils.new_id(),
        team_id=team_id,
        token=utils.generate_link(),
        created_by_cpo_id=cfg.cpos[0].id,
        created_at=_now(),
        expires_at=_now(),
    )
    storage.create_invite(invite)
    assert [i.id for i in storage.list_invites(team_id)] == [invite.id]
    assert storage.list_invites("other-team") == []


def test_delete_invite(tmp_path):
    cfg = _make_config(tmp_path)
    storage.save_config(cfg)
    team_id = cfg.teams[0].id
    invite = TeamInvite(
        id=utils.new_id(),
        team_id=team_id,
        token=utils.generate_link(),
        created_by_cpo_id=cfg.cpos[0].id,
        created_at=_now(),
        expires_at=_now(),
    )
    storage.create_invite(invite)
    assert storage.delete_invite(team_id, invite.id) is True
    assert storage.get_invite_by_token(invite.token) is None
    assert storage.delete_invite(team_id, invite.id) is False


def test_mark_invite_used(tmp_path):
    cfg = _make_config(tmp_path)
    storage.save_config(cfg)
    team_id = cfg.teams[0].id
    invite = TeamInvite(
        id=utils.new_id(),
        team_id=team_id,
        token=utils.generate_link(),
        created_by_cpo_id=cfg.cpos[0].id,
        created_at=_now(),
        expires_at=_now(),
    )
    storage.create_invite(invite)
    assert storage.mark_invite_used(invite.id, _now().isoformat()) is True
    loaded = storage.get_invite_by_token(invite.token)
    assert loaded.used_at is not None
    # Single-use: marking again fails since used_at is no longer NULL.
    assert storage.mark_invite_used(invite.id, _now().isoformat()) is False


def test_find_team_by_link(tmp_path):
    cfg = _make_config(tmp_path)
    storage.save_config(cfg)
    found = storage.find_team_by_link(cfg.teams[0].unique_link)
    assert found is not None
    assert found.id == cfg.teams[0].id
    assert storage.find_team_by_link("no-such-link") is None


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
