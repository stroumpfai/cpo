"""
Public order submission service (no auth required).

Rate limiting is enforced in-process via a monotonic timestamp per client IP.
The store resets on server restart, which is acceptable for the MVP.
"""
import time
from datetime import datetime, timezone

from fastapi import HTTPException, status

from config import RATE_LIMIT_SECONDS
from models import Order, PizzaResponse, SessionStatusResponse, SubmitOrderResponse
from storage import add_order_to_session, find_cpo_by_link, list_sessions, load_menu
from utils import compute_session_status, new_id

# {client_ip: monotonic timestamp of last successful submission attempt}
_rate_limit: dict[str, float] = {}


def clear_rate_limit() -> None:
    """Reset in-process rate limit store (for tests)."""
    _rate_limit.clear()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _best_session(cpo_id: str):
    """Return (session, status) for the most relevant session: active > upcoming > latest closed."""
    sessions = list_sessions(cpo_id)
    best_upcoming = None
    for s in reversed(sessions):
        st = compute_session_status(s.session_date, s.start_time, s.end_time, s.grace_period_minutes)
        if st == "active":
            return s, "active"
        if st == "upcoming" and best_upcoming is None:
            best_upcoming = s
    if best_upcoming is not None:
        return best_upcoming, "upcoming"
    if sessions:
        last = sessions[-1]
        st = compute_session_status(last.session_date, last.start_time, last.end_time, last.grace_period_minutes)
        return last, st
    return None, "closed"


def _resolve_link(unique_link: str):
    """Return (cpo, session, status) for a team link, raising 404 if link unknown."""
    cpo = find_cpo_by_link(unique_link)
    if cpo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team link not found")
    session, sess_status = _best_session(cpo.id)
    return cpo, session, sess_status


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_session_status(unique_link: str) -> SessionStatusResponse:
    cpo, session, sess_status = _resolve_link(unique_link)

    if session is None:
        return SessionStatusResponse(
            session_id="",
            status="closed",
            team_name=cpo.team_name,
            pizzas=[],
            message="No active session",
        )

    menu = load_menu(cpo.id)
    pizzas = [PizzaResponse(id=p.id, name=p.name, price=p.price) for p in menu.pizzas]

    message = "Session is closed" if sess_status == "closed" else None

    return SessionStatusResponse(
        session_id=session.id,
        status=sess_status,
        team_name=cpo.team_name,
        pizzas=pizzas,
        message=message,
        session_date=str(session.session_date),
        end_time=session.end_time,
    )


def submit_order(
    unique_link: str,
    member_name: str,
    pizza_ids: list[str],
    client_ip: str,
) -> SubmitOrderResponse:
    # Rate limit: check before doing any work
    now = time.monotonic()
    last = _rate_limit.get(client_ip)
    if last is not None and (now - last) < RATE_LIMIT_SECONDS:
        wait = RATE_LIMIT_SECONDS - (now - last)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many requests. Please wait {RATE_LIMIT_SECONDS} seconds before trying again.",
            headers={
                "X-RateLimit-Limit": "1",
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(time.time() + wait)),
                "Retry-After": str(int(wait) + 1),
            },
        )

    # Consume the rate limit slot immediately (even if subsequent validation fails)
    _rate_limit[client_ip] = now

    cpo, session, sess_status = _resolve_link(unique_link)

    if session is None or sess_status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Session is closed")

    menu = load_menu(cpo.id)
    pizza_map = {p.id: p for p in menu.pizzas}

    order_ids: list[str] = []
    created_at = datetime.now(tz=timezone.utc)

    for pizza_id in pizza_ids:
        pizza = pizza_map.get(pizza_id)
        if pizza is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Pizza '{pizza_id}' not found in menu",
            )
        order = Order(
            id=new_id(),
            session_id=session.id,
            member_name=member_name,
            pizza_id=pizza.id,
            pizza_name=pizza.name,
            pizza_price=pizza.price,
            total_price=pizza.price,
            created_at=created_at,
            client_ip=client_ip,
        )
        add_order_to_session(cpo.id, session.id, order)
        order_ids.append(order.id)

    return SubmitOrderResponse(
        status="submitted",
        member_name=member_name,
        orders_created=len(order_ids),
        order_ids=order_ids,
    )
