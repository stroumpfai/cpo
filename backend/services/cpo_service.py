from datetime import date, timezone, datetime

from fastapi import HTTPException, status

from models import CPORecord, Pizza, SessionFile
from storage import (
    delete_order_from_session,
    list_sessions,
    load_config,
    load_menu,
    load_session,
    save_menu,
    save_session,
)
from utils import compute_session_status, new_id


# ---------------------------------------------------------------------------
# CPO profile
# ---------------------------------------------------------------------------

def get_cpo(cpo_id: str) -> CPORecord:
    cfg = load_config()
    cpo = next((c for c in cfg.cpos if c.id == cpo_id), None)
    if cpo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CPO not found")
    return cpo


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
    for s in list_sessions(cpo.id):
        st = compute_session_status(s.session_date, s.start_time, s.end_time, s.grace_period_minutes)
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


# ---------------------------------------------------------------------------
# Order deletion (CPO action)
# ---------------------------------------------------------------------------

def delete_order(cpo_id: str, order_id: str) -> None:
    for session in list_sessions(cpo_id):
        if delete_order_from_session(cpo_id, session.id, order_id):
            return
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
