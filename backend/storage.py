"""
SQLite persistence layer (SQLAlchemy Core).

Public API is unchanged from the JSON-file era: functions accept and return
the Pydantic models from models.py (ConfigFile, Menu, SessionFile, Order).
Tables live in schema.py; the engine in db.py.

Concurrency: every function runs in its own transaction; SQLite serializes
writers and WAL keeps readers unblocked, so no application-level lock is
needed. save_session() upserts the session row and upserts the orders it
carries but NEVER deletes orders — a stale in-memory copy (e.g. close_session's
load → set closed_at → save) cannot clobber an order inserted concurrently.
Order deletion only happens through delete_order_from_session().
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Optional

from sqlalchemy import delete, func, select, text, update
from sqlalchemy.dialects.sqlite import insert

import schema as S
from db import get_engine
from models import (
    AdminRecord,
    ConfigFile,
    CPORecord,
    Menu,
    Order,
    Pizza,
    SessionFile,
    SessionUsageRow,
    StatsSessionUsageRow,
)
from utils import new_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _upsert(table, values: dict):
    """INSERT ... ON CONFLICT(pk) DO UPDATE for a single row."""
    stmt = insert(table).values(**values)
    pk_cols = [c.name for c in table.primary_key.columns]
    update_cols = {k: stmt.excluded[k] for k in values if k not in pk_cols}
    return stmt.on_conflict_do_update(index_elements=pk_cols, set_=update_cols)


def _orders_for_sessions(conn, session_ids: list[str]) -> dict[str, list[Order]]:
    """Load orders for the given sessions, preserving insertion order."""
    grouped: dict[str, list[Order]] = defaultdict(list)
    if not session_ids:
        return grouped
    rows = conn.execute(
        select(S.orders)
        .where(S.orders.c.session_id.in_(session_ids))
        # rowid preserves insertion order, like the old JSON orders array
        .order_by(text("rowid"))
    )
    for row in rows:
        grouped[row.session_id].append(Order.model_validate(dict(row._mapping)))
    return grouped


def _session_from_row(row, orders: list[Order]) -> SessionFile:
    data = dict(row._mapping)
    data["orders"] = orders
    return SessionFile.model_validate(data)


# ---------------------------------------------------------------------------
# Config (admin + CPO accounts)
# ---------------------------------------------------------------------------

def load_config() -> ConfigFile:
    with get_engine().begin() as conn:
        admin_rows = conn.execute(select(S.admins).order_by(S.admins.c.id)).all()
        if not admin_rows:
            raise FileNotFoundError(
                "No admin account in the database. "
                "Create one with scripts/create_admin.py."
            )
        admin_list = [AdminRecord.model_validate(dict(r._mapping)) for r in admin_rows]
        cpo_rows = conn.execute(select(S.cpos).order_by(S.cpos.c.created_at))
        cpo_list = [CPORecord.model_validate(dict(r._mapping)) for r in cpo_rows]
    return ConfigFile(admins=admin_list, cpos=cpo_list)


def save_config(cfg: ConfigFile) -> None:
    with get_engine().begin() as conn:
        # Admins are only upserted, never delete-synced: a stale in-memory
        # config must not silently drop admin accounts. Deletion goes through
        # delete_admin() exclusively.
        for admin in cfg.admins:
            conn.execute(_upsert(S.admins, admin.model_dump(mode="json")))
        for cpo in cfg.cpos:
            conn.execute(_upsert(S.cpos, cpo.model_dump(mode="json")))
        # CPOs absent from cfg were deleted; cascades remove their
        # menus, sessions and orders (the JSON layout left them orphaned).
        ids = [c.id for c in cfg.cpos]
        stmt = delete(S.cpos)
        if ids:
            stmt = stmt.where(S.cpos.c.id.not_in(ids))
        conn.execute(stmt)


def update_cpo_fields(cpo_id: str, **fields) -> Optional[CPORecord]:
    """Update named columns on a single CPO row, leaving every other column alone.

    Settings changes must NOT go through load_config()/save_config(): that is a
    read-modify-write of the entire config, so two concurrent single-field
    updates each write back their own stale snapshot and the later one silently
    reverts the earlier. The settings page saves team name, currency and member
    identifier in parallel, which loses updates most of the time. A targeted
    UPDATE touches only the named columns, so parallel writes to different
    fields cannot clobber one another.

    Returns the refreshed record, or None if no CPO has that id.
    """
    unknown = set(fields) - set(S.cpos.c.keys())
    if unknown:
        raise ValueError(f"Unknown cpos column(s): {sorted(unknown)}")
    with get_engine().begin() as conn:
        if fields:
            conn.execute(update(S.cpos).where(S.cpos.c.id == cpo_id).values(**fields))
        row = conn.execute(select(S.cpos).where(S.cpos.c.id == cpo_id)).first()
    return CPORecord.model_validate(dict(row._mapping)) if row else None


def insert_admin(username: str, password_hash: str, created_at: str) -> AdminRecord:
    """Insert a new admin, letting SQLite assign the id."""
    with get_engine().begin() as conn:
        result = conn.execute(
            S.admins.insert().values(
                username=username,
                password_hash=password_hash,
                created_at=created_at,
            )
        )
        admin_id = result.inserted_primary_key[0]
    return AdminRecord(
        id=admin_id,
        username=username,
        password_hash=password_hash,
        created_at=created_at,
    )


def delete_admin(admin_id: int) -> bool:
    with get_engine().begin() as conn:
        result = conn.execute(delete(S.admins).where(S.admins.c.id == admin_id))
    return result.rowcount > 0


# ---------------------------------------------------------------------------
# Menus
#
# Invariant (kept inside each transaction): if a CPO has any menus, exactly
# one has is_default = 1 — backed by the ux_menus_one_default partial unique
# index. The index is checked per statement, so default swaps must always
# UNSET the old default before SETTING the new one.
# ---------------------------------------------------------------------------

def _pizzas_for_menus(conn, menu_ids: list[str]) -> dict[str, list[Pizza]]:
    """Load pizzas for the given menus, preserving insertion order."""
    grouped: dict[str, list[Pizza]] = defaultdict(list)
    if not menu_ids:
        return grouped
    rows = conn.execute(
        select(S.pizzas)
        .where(S.pizzas.c.menu_id.in_(menu_ids))
        .order_by(text("rowid"))
    )
    for row in rows:
        grouped[row.menu_id].append(Pizza.model_validate(dict(row._mapping)))
    return grouped


def _menu_from_row(row, pizzas: list[Pizza]) -> Menu:
    data = dict(row._mapping)
    data["pizzas"] = pizzas
    return Menu.model_validate(data)


def list_menus(cpo_id: str) -> list[Menu]:
    """All menus of a CPO in creation order, pizzas included."""
    with get_engine().begin() as conn:
        rows = conn.execute(
            select(S.menus).where(S.menus.c.cpo_id == cpo_id).order_by(text("rowid"))
        ).all()
        grouped = _pizzas_for_menus(conn, [r.id for r in rows])
    return [_menu_from_row(r, grouped[r.id]) for r in rows]


def _load_one_menu(conn, *where) -> Optional[Menu]:
    row = conn.execute(select(S.menus).where(*where)).first()
    if row is None:
        return None
    pizzas = _pizzas_for_menus(conn, [row.id])[row.id]
    return _menu_from_row(row, pizzas)


def get_menu(cpo_id: str, menu_id: str) -> Optional[Menu]:
    with get_engine().begin() as conn:
        return _load_one_menu(
            conn, S.menus.c.id == menu_id, S.menus.c.cpo_id == cpo_id
        )


def get_default_menu(cpo_id: str) -> Optional[Menu]:
    with get_engine().begin() as conn:
        return _load_one_menu(
            conn, S.menus.c.cpo_id == cpo_id, S.menus.c.is_default == 1
        )


def create_menu(cpo_id: str, name: str, pizzeria_url: str | None = None) -> Menu:
    """Insert an empty menu; the CPO's first menu becomes the default."""
    with get_engine().begin() as conn:
        has_menus = conn.execute(
            select(S.menus.c.id).where(S.menus.c.cpo_id == cpo_id).limit(1)
        ).first()
        menu = Menu(
            id=new_id(),
            cpo_id=cpo_id,
            name=name,
            is_default=has_menus is None,
            pizzeria_url=pizzeria_url,
        )
        conn.execute(
            S.menus.insert().values(
                id=menu.id,
                cpo_id=menu.cpo_id,
                name=menu.name,
                is_default=int(menu.is_default),
                pizzeria_url=menu.pizzeria_url,
            )
        )
    return menu


def save_menu(menu: Menu) -> None:
    """Update name/url and full-replace the pizza list of an existing menu.

    Deliberately never writes is_default — a stale in-memory Menu must not
    be able to violate the one-default invariant; use set_default_menu().
    """
    with get_engine().begin() as conn:
        result = conn.execute(
            update(S.menus)
            .where(S.menus.c.id == menu.id, S.menus.c.cpo_id == menu.cpo_id)
            .values(name=menu.name, pizzeria_url=menu.pizzeria_url)
        )
        if result.rowcount == 0:
            raise ValueError(f"Menu {menu.id} not found")
        conn.execute(delete(S.pizzas).where(S.pizzas.c.menu_id == menu.id))
        if menu.pizzas:
            conn.execute(
                S.pizzas.insert(),
                [{"menu_id": menu.id, **p.model_dump(mode="json")} for p in menu.pizzas],
            )


def set_default_menu(cpo_id: str, menu_id: str) -> bool:
    with get_engine().begin() as conn:
        target = conn.execute(
            select(S.menus.c.id).where(
                S.menus.c.id == menu_id, S.menus.c.cpo_id == cpo_id
            )
        ).first()
        if target is None:
            return False
        conn.execute(
            update(S.menus)
            .where(S.menus.c.cpo_id == cpo_id, S.menus.c.is_default == 1)
            .values(is_default=0)
        )
        conn.execute(
            update(S.menus).where(S.menus.c.id == menu_id).values(is_default=1)
        )
    return True


def delete_menu(cpo_id: str, menu_id: str) -> bool:
    """Delete a menu (pizzas cascade, sessions.menu_id is set to NULL).

    If the deleted menu was the default, the oldest remaining menu is
    promoted so the one-default invariant holds whenever menus exist.
    """
    with get_engine().begin() as conn:
        row = conn.execute(
            select(S.menus.c.is_default).where(
                S.menus.c.id == menu_id, S.menus.c.cpo_id == cpo_id
            )
        ).first()
        if row is None:
            return False
        conn.execute(delete(S.menus).where(S.menus.c.id == menu_id))
        if row.is_default:
            oldest = (
                select(S.menus.c.id)
                .where(S.menus.c.cpo_id == cpo_id)
                .order_by(text("rowid"))
                .limit(1)
                .scalar_subquery()
            )
            conn.execute(
                update(S.menus).where(S.menus.c.id == oldest).values(is_default=1)
            )
    return True


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

def load_session(cpo_id: str, session_id: str) -> Optional[SessionFile]:
    with get_engine().begin() as conn:
        row = conn.execute(
            select(S.sessions).where(
                S.sessions.c.id == session_id, S.sessions.c.cpo_id == cpo_id
            )
        ).first()
        if row is None:
            return None
        orders = _orders_for_sessions(conn, [session_id])[session_id]
    return _session_from_row(row, orders)


def save_session(session: SessionFile) -> None:
    data = session.model_dump(mode="json")
    order_dicts = data.pop("orders")
    with get_engine().begin() as conn:
        conn.execute(_upsert(S.sessions, data))
        for order in order_dicts:
            conn.execute(_upsert(S.orders, order))


def list_sessions(cpo_id: str) -> list[SessionFile]:
    with get_engine().begin() as conn:
        rows = conn.execute(
            select(S.sessions)
            .where(S.sessions.c.cpo_id == cpo_id)
            .order_by(S.sessions.c.created_at)
        ).all()
        grouped = _orders_for_sessions(conn, [r.id for r in rows])
    return [_session_from_row(r, grouped[r.id]) for r in rows]


def list_session_stats() -> list[SessionUsageRow]:
    """All sessions across all CPOs with per-session order counts.

    Loads no order rows (counts only) so it stays O(2 queries) regardless
    of how many sessions/orders exist. Status (upcoming/active/closed) is
    NOT computed here; callers use utils.compute_session_status().
    """
    with get_engine().begin() as conn:
        counts = dict(
            conn.execute(
                select(S.orders.c.session_id, func.count())
                .group_by(S.orders.c.session_id)
            ).all()
        )
        rows = conn.execute(select(S.sessions)).all()
    return [
        SessionUsageRow.model_validate({**dict(r._mapping), "order_count": counts.get(r.id, 0)})
        for r in rows
    ]


# ---------------------------------------------------------------------------
# CPO statistics page
#
# All three functions accept an optional `since` cutoff (a CPO's
# stats_reset_at) filtered on sessions.created_at — the real wall-clock
# moment a session was opened, not the scheduled session_date, so "reset"
# has an unambiguous, immediate effect. Like list_session_stats(), these
# stay GROUP BY-only queries and never load raw order rows.
# ---------------------------------------------------------------------------

def get_recent_sessions(
    cpo_id: str, limit: int = 5, since: Optional[datetime] = None
) -> list[StatsSessionUsageRow]:
    """Most recent sessions (any status) for a CPO, with summed item counts."""
    with get_engine().begin() as conn:
        query = select(S.sessions).where(S.sessions.c.cpo_id == cpo_id)
        if since is not None:
            query = query.where(S.sessions.c.created_at >= since.isoformat())
        query = query.order_by(
            S.sessions.c.session_date.desc(),
            S.sessions.c.start_time.desc(),
            S.sessions.c.created_at.desc(),
        ).limit(limit)
        rows = conn.execute(query).all()

        session_ids = [r.id for r in rows]
        item_counts = dict(
            conn.execute(
                select(S.orders.c.session_id, func.sum(S.orders.c.quantity))
                .where(S.orders.c.session_id.in_(session_ids))
                .group_by(S.orders.c.session_id)
            ).all()
        ) if session_ids else {}

    return [
        StatsSessionUsageRow.model_validate(
            {**dict(r._mapping), "item_count": item_counts.get(r.id, 0)}
        )
        for r in rows
    ]


def get_menu_stats(cpo_id: str, since: Optional[datetime] = None) -> list[dict]:
    """Per-menu use count + top-3 plates/people, for every menu the CPO owns.

    Orders whose session lost its menu (deleted menu -> menu_id NULL) are
    excluded here on purpose; they still count toward get_general_stats().
    """
    with get_engine().begin() as conn:
        menu_rows = conn.execute(
            select(S.menus.c.id, S.menus.c.name)
            .where(S.menus.c.cpo_id == cpo_id)
            .order_by(text("rowid"))
        ).all()

        session_filter = [S.sessions.c.cpo_id == cpo_id, S.sessions.c.menu_id.is_not(None)]
        if since is not None:
            session_filter.append(S.sessions.c.created_at >= since.isoformat())

        use_counts = dict(
            conn.execute(
                select(S.sessions.c.menu_id, func.count())
                .where(*session_filter)
                .group_by(S.sessions.c.menu_id)
            ).all()
        )

        joined = S.orders.join(S.sessions, S.orders.c.session_id == S.sessions.c.id)
        plate_rows = conn.execute(
            select(S.sessions.c.menu_id, S.orders.c.pizza_name, func.sum(S.orders.c.quantity))
            .select_from(joined)
            .where(*session_filter)
            .group_by(S.sessions.c.menu_id, S.orders.c.pizza_name)
        ).all()
        people_rows = conn.execute(
            select(S.sessions.c.menu_id, S.orders.c.member_name, func.sum(S.orders.c.quantity))
            .select_from(joined)
            .where(*session_filter)
            .group_by(S.sessions.c.menu_id, S.orders.c.member_name)
        ).all()

    plate_counts: dict[str, dict[str, int]] = defaultdict(dict)
    for menu_id, pizza_name, count in plate_rows:
        plate_counts[menu_id][pizza_name] = count
    people_counts: dict[str, dict[str, int]] = defaultdict(dict)
    for menu_id, member_name, count in people_rows:
        people_counts[menu_id][member_name] = count

    def top3(counts: dict[str, int]) -> list[tuple[str, int]]:
        # Ties broken alphabetically for a stable, predictable ranking.
        return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:3]

    return [
        {
            "menu_id": m.id,
            "menu_name": m.name,
            "use_count": use_counts.get(m.id, 0),
            "top_plates": top3(plate_counts.get(m.id, {})),
            "top_people": top3(people_counts.get(m.id, {})),
        }
        for m in menu_rows
    ]


def get_general_stats(cpo_id: str, since: Optional[datetime] = None) -> dict:
    """Total sessions + distinct member/plate counts across a CPO's whole history."""
    with get_engine().begin() as conn:
        session_filter = [S.sessions.c.cpo_id == cpo_id]
        if since is not None:
            session_filter.append(S.sessions.c.created_at >= since.isoformat())

        total_sessions = conn.execute(
            select(func.count()).select_from(S.sessions).where(*session_filter)
        ).scalar_one()

        distinct_row = conn.execute(
            select(
                func.count(func.distinct(S.orders.c.member_name)),
                func.count(func.distinct(S.orders.c.pizza_name)),
            )
            .select_from(S.orders.join(S.sessions, S.orders.c.session_id == S.sessions.c.id))
            .where(*session_filter)
        ).first()

    return {
        "total_sessions": total_sessions,
        "distinct_members": distinct_row[0] or 0,
        "distinct_plates": distinct_row[1] or 0,
    }


def find_cpo_by_link(unique_link: str) -> Optional[CPORecord]:
    """Return the CPO whose permanent team link matches unique_link."""
    with get_engine().begin() as conn:
        row = conn.execute(
            select(S.cpos).where(S.cpos.c.unique_link == unique_link)
        ).first()
    return CPORecord.model_validate(dict(row._mapping)) if row else None


def find_session_by_link(unique_link: str) -> Optional[tuple[str, SessionFile]]:
    """Return (cpo_id, session) for the most recent session of the CPO owning unique_link."""
    with get_engine().begin() as conn:
        cpo_row = conn.execute(
            select(S.cpos.c.id).where(S.cpos.c.unique_link == unique_link)
        ).first()
        if cpo_row is None:
            return None
        row = conn.execute(
            select(S.sessions)
            .where(S.sessions.c.cpo_id == cpo_row.id)
            .order_by(S.sessions.c.created_at.desc())
            .limit(1)
        ).first()
        if row is None:
            return None
        orders = _orders_for_sessions(conn, [row.id])[row.id]
    return cpo_row.id, _session_from_row(row, orders)


# ---------------------------------------------------------------------------
# Order mutations
# ---------------------------------------------------------------------------

def add_orders_to_session(cpo_id: str, session_id: str, orders: list[Order]) -> None:
    with get_engine().begin() as conn:
        exists = conn.execute(
            select(S.sessions.c.id).where(
                S.sessions.c.id == session_id, S.sessions.c.cpo_id == cpo_id
            )
        ).first()
        if exists is None:
            raise ValueError(f"Session {session_id} not found")
        if orders:
            conn.execute(
                S.orders.insert(), [o.model_dump(mode="json") for o in orders]
            )


def add_order_to_session(cpo_id: str, session_id: str, order: Order) -> None:
    add_orders_to_session(cpo_id, session_id, [order])


def _owned_session_ids(cpo_id: str, session_id: str):
    return select(S.sessions.c.id).where(
        S.sessions.c.id == session_id, S.sessions.c.cpo_id == cpo_id
    )


def delete_order_from_session(cpo_id: str, session_id: str, order_id: str) -> bool:
    with get_engine().begin() as conn:
        result = conn.execute(
            delete(S.orders).where(
                S.orders.c.id == order_id,
                S.orders.c.session_id.in_(_owned_session_ids(cpo_id, session_id)),
            )
        )
    return result.rowcount > 0


def set_order_received(cpo_id: str, session_id: str, order_id: str, received: bool) -> bool:
    with get_engine().begin() as conn:
        result = conn.execute(
            update(S.orders)
            .where(
                S.orders.c.id == order_id,
                S.orders.c.session_id.in_(_owned_session_ids(cpo_id, session_id)),
            )
            .values(received=received)
        )
    return result.rowcount > 0
