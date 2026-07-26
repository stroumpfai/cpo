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
