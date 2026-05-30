import asyncio
import json
from datetime import date, timezone, datetime
from typing import AsyncGenerator

from fastapi import HTTPException, status

from models import CPORecord, Pizza, SessionFile
from password_policy import validate_password
from storage import (
    delete_order_from_session,
    list_sessions,
    load_config,
    load_menu,
    load_session,
    save_config,
    save_menu,
    save_session,
    set_order_received as storage_set_order_received,
)
from utils import compute_session_status, hash_password, new_id, verify_password


# ---------------------------------------------------------------------------
# CPO profile
# ---------------------------------------------------------------------------

def get_cpo(cpo_id: str) -> CPORecord:
    cfg = load_config()
    cpo = next((c for c in cfg.cpos if c.id == cpo_id), None)
    if cpo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CPO not found")
    return cpo


def update_currency(cpo_id: str, currency: str) -> CPORecord:
    cfg = load_config()
    cpo = next((c for c in cfg.cpos if c.id == cpo_id), None)
    if cpo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CPO not found")
    cpo.currency = currency.strip()
    save_config(cfg)
    return cpo


def change_password(cpo_id: str, current_password: str, new_password: str) -> None:
    cfg = load_config()
    cpo = next((c for c in cfg.cpos if c.id == cpo_id), None)
    if cpo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CPO not found")
    if not verify_password(current_password, cpo.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect.",
        )
    validate_password(new_password, cpo.username)
    cpo.password_hash = hash_password(new_password)
    cpo.token_version += 1
    save_config(cfg)


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

def _session_to_dict(session: SessionFile, unique_link: str) -> dict:
    return {
        "id": session.id,
        "cpo_id": session.cpo_id,
        "team_name": session.team_name,
        "unique_link": unique_link,
        "session_date": session.session_date,
        "start_time": session.start_time,
        "end_time": session.end_time,
        "grace_period_minutes": session.grace_period_minutes,
        "status": compute_session_status(
            session.session_date,
            session.start_time,
            session.end_time,
            session.grace_period_minutes,
            session.closed_at,
        ),
        "created_at": session.created_at,
    }


def create_session(
    cpo: CPORecord,
    session_date: date,
    start_time: str,
    end_time: str,
    grace_period_minutes: int,
) -> dict:
    # Reject sessions whose close time has already passed — they would be
    # created as "closed" and never accept any orders.
    if compute_session_status(session_date, start_time, end_time, grace_period_minutes) == "closed":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Session end time has already passed. Please set a future end time.",
        )

    for s in list_sessions(cpo.id):
        st = compute_session_status(s.session_date, s.start_time, s.end_time, s.grace_period_minutes, s.closed_at)
        if st in ("upcoming", "active"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="CPO already has an active or upcoming session",
            )

    session = SessionFile(
        id=new_id(),
        cpo_id=cpo.id,
        team_name=cpo.team_name,
        session_date=session_date,
        start_time=start_time,
        end_time=end_time,
        grace_period_minutes=grace_period_minutes,
        created_at=datetime.now(tz=timezone.utc),
    )
    save_session(session)
    return _session_to_dict(session, cpo.unique_link)


def get_sessions(cpo: CPORecord) -> list[dict]:
    return [_session_to_dict(s, cpo.unique_link) for s in list_sessions(cpo.id)]


def get_session_or_404(cpo_id: str, session_id: str) -> SessionFile:
    session = load_session(cpo_id, session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return session


# ---------------------------------------------------------------------------
# Menu
# ---------------------------------------------------------------------------

def get_menu_pizzas(cpo_id: str) -> list[Pizza]:
    return load_menu(cpo_id).pizzas


def add_pizza(cpo_id: str, name: str, price: float) -> Pizza:
    menu = load_menu(cpo_id)
    if any(p.name.lower() == name.lower() for p in menu.pizzas):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Pizza name already exists")
    pizza = Pizza(id=new_id(), name=name, price=price)
    menu.pizzas.append(pizza)
    save_menu(menu)
    return pizza


def update_pizza(cpo_id: str, pizza_id: str, name: str, price: float) -> Pizza:
    menu = load_menu(cpo_id)
    pizza = next((p for p in menu.pizzas if p.id == pizza_id), None)
    if pizza is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pizza not found")
    if any(p.name.lower() == name.lower() and p.id != pizza_id for p in menu.pizzas):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Pizza name already exists")
    pizza.name = name
    pizza.price = price
    save_menu(menu)
    return pizza


def delete_pizza(cpo_id: str, pizza_id: str) -> None:
    menu = load_menu(cpo_id)
    before = len(menu.pizzas)
    menu.pizzas = [p for p in menu.pizzas if p.id != pizza_id]
    if len(menu.pizzas) == before:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pizza not found")
    save_menu(menu)


def get_pizzeria_url(cpo_id: str) -> str | None:
    return load_menu(cpo_id).pizzeria_url


def set_pizzeria_url(cpo_id: str, pizzeria_url: str | None) -> str | None:
    menu = load_menu(cpo_id)
    menu.pizzeria_url = pizzeria_url
    save_menu(menu)
    return pizzeria_url


# ---------------------------------------------------------------------------
# Order deletion (CPO action)
# ---------------------------------------------------------------------------

def delete_order(cpo_id: str, order_id: str) -> None:
    for session in list_sessions(cpo_id):
        if delete_order_from_session(cpo_id, session.id, order_id):
            return
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")


def set_order_received(cpo_id: str, order_id: str, received: bool) -> None:
    for session in list_sessions(cpo_id):
        if storage_set_order_received(cpo_id, session.id, order_id, received):
            return
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")


# ---------------------------------------------------------------------------
# Force-close session
# ---------------------------------------------------------------------------

def close_session(cpo_id: str, session_id: str) -> dict:
    session = load_session(cpo_id, session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    current_status = compute_session_status(
        session.session_date, session.start_time, session.end_time,
        session.grace_period_minutes, session.closed_at,
    )
    if current_status == "closed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Session is already closed",
        )

    session.closed_at = datetime.now(tz=timezone.utc)
    save_session(session)

    cpo = get_cpo(cpo_id)
    return _session_to_dict(session, cpo.unique_link)


# ---------------------------------------------------------------------------
# SSE streaming
# ---------------------------------------------------------------------------

async def session_sse_events(cpo_id: str, session_id: str) -> AsyncGenerator[str, None]:
    """
    Async generator that yields SSE-formatted strings.

    Polls the session file every second and emits an "update" event whenever
    the order count or status changes.  Terminates (and emits "session_closed")
    once the session is past its grace period.
    """
    from services.summary_service import build_summary

    last_hash: str | None = None

    while True:
        session = await asyncio.to_thread(load_session, cpo_id, session_id)
        if session is None:
            yield "event: error\ndata: " + json.dumps({"message": "session not found"}) + "\n\n"
            return

        sess_status = compute_session_status(
            session.session_date,
            session.start_time,
            session.end_time,
            session.grace_period_minutes,
            session.closed_at,
        )
        received_bits = ",".join(
            f"{o.id}:{int(o.received)}" for o in sorted(session.orders, key=lambda o: o.id)
        )
        current_hash = f"{len(session.orders)}-{sess_status}-{received_bits}"

        if current_hash != last_hash:
            last_hash = current_hash
            summary = build_summary(session)
            event_type = "session_closed" if sess_status == "closed" else "update"
            yield f"event: {event_type}\ndata: {summary.model_dump_json()}\n\n"

        if sess_status == "closed":
            return

        await asyncio.sleep(1)
