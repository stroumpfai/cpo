"""
Public order submission service (no auth required).

Rate limiting is enforced in-process via a monotonic timestamp per client IP.
The store resets on server restart, which is acceptable for the MVP. It also
assumes a single uvicorn process (see the Dockerfile CMD comment) — running
multiple workers/replicas would give each its own store and split the rate
limit across them.
"""
import time
from datetime import datetime, timezone

from email_validator import EmailNotValidError, validate_email
from fastapi import HTTPException, status

from config import RATE_LIMIT_SECONDS
from models import (
    Menu,
    Order,
    OrderItem,
    PizzaResponse,
    SessionFile,
    SessionStatusResponse,
    SubmitOrderResponse,
)
from storage import (
    add_orders_to_session,
    find_team_by_link,
    get_default_menu,
    get_menu,
    list_sessions,
)
from utils import compute_session_status, new_id

# {client_ip: monotonic timestamp of last successful submission attempt}
_rate_limit: dict[str, float] = {}

_MAX_NAME_LEN = 100    # unchanged from the original OrderItem cap
_MAX_EMAIL_LEN = 254   # RFC 5321 max forward-path length


def clear_rate_limit() -> None:
    """Reset in-process rate limit store (for tests)."""
    _rate_limit.clear()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _best_session(team_id: str):
    """Return (session, status) for the most relevant session: active > upcoming > latest closed."""
    sessions = list_sessions(team_id)
    best_upcoming = None
    for s in reversed(sessions):
        st = compute_session_status(s.session_date, s.start_time, s.end_time, s.grace_period_minutes, s.closed_at)
        if st == "active":
            return s, "active"
        if st == "upcoming" and best_upcoming is None:
            best_upcoming = s
    if best_upcoming is not None:
        return best_upcoming, "upcoming"
    if sessions:
        last = sessions[-1]
        st = compute_session_status(last.session_date, last.start_time, last.end_time, last.grace_period_minutes, last.closed_at)
        return last, st
    return None, "closed"


def _resolve_link(unique_link: str):
    """Return (team, session, status) for a team link, raising 404 if link unknown."""
    team = find_team_by_link(unique_link)
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team link not found")
    session, sess_status = _best_session(team.id)
    return team, session, sess_status


def _normalize_member_value(raw: str, mode: str) -> str:
    """Validate and normalise the identity a team member typed, per the CPO's mode.

    Lives here rather than on OrderItem because the Pydantic model has no way to
    know which CPO the unique_link belongs to.
    """
    value = raw.strip()

    if mode != "email":
        if not value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Name is required.",
            )
        if len(value) > _MAX_NAME_LEN:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Name must be {_MAX_NAME_LEN} characters or fewer.",
            )
        return value

    if not value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email address is required.",
        )
    if len(value) > _MAX_EMAIL_LEN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Email address must be {_MAX_EMAIL_LEN} characters or fewer.",
        )
    try:
        # check_deliverability=False is load-bearing: the default is True, which
        # would fire a DNS MX lookup for every item in every submitted cart.
        result = validate_email(value, check_deliverability=False)
    except EmailNotValidError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"'{value[:80]}' is not a valid email address.",
        ) from None
    # .normalized only lower-cases the domain. Lower the whole address so the
    # dashboard's case-sensitive distinct-member count treats Alice@x and
    # alice@x as one person.
    return result.normalized.lower()


def _menu_for_session(team_id: str, session: SessionFile | None) -> Menu | None:
    """The menu a session serves; falls back to the team's default menu for
    legacy sessions (menu_id NULL) or after the referenced menu was deleted."""
    if session is not None and session.menu_id:
        menu = get_menu(team_id, session.menu_id)
        if menu is not None:
            return menu
    return get_default_menu(team_id)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_session_status(unique_link: str) -> SessionStatusResponse:
    team, session, sess_status = _resolve_link(unique_link)

    menu = _menu_for_session(team.id, session)
    pizzeria_url = menu.pizzeria_url if menu else None

    if session is None:
        return SessionStatusResponse(
            session_id="",
            status="closed",
            team_name=team.team_name,
            pizzas=[],
            message="No active session",
            pizzeria_url=pizzeria_url,
            currency=team.currency,
            member_identifier=team.member_identifier,
        )

    pizzas = [
        PizzaResponse(id=p.id, name=p.name, price=p.price)
        for p in (menu.pizzas if menu else [])
    ]
    message = "Session is closed" if sess_status == "closed" else None

    return SessionStatusResponse(
        session_id=session.id,
        status=sess_status,
        team_name=team.team_name,
        pizzas=pizzas,
        message=message,
        session_date=str(session.session_date),
        end_time=session.end_time,
        pizzeria_url=pizzeria_url,
        currency=team.currency,
        member_identifier=team.member_identifier,
    )


def submit_order(
    unique_link: str,
    items: list[OrderItem],
    client_ip: str,
) -> SubmitOrderResponse:
    # Rate limit: check before doing any work
    now = time.monotonic()
    # Evict IPs whose window has long expired to prevent unbounded growth
    stale = [ip for ip, ts in _rate_limit.items() if now - ts >= RATE_LIMIT_SECONDS * 2]
    for ip in stale:
        del _rate_limit[ip]
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

    team, session, sess_status = _resolve_link(unique_link)

    if session is None or sess_status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Session is closed")

    menu = _menu_for_session(team.id, session)
    pizza_map = {p.id: p for p in menu.pizzas} if menu else {}

    created_at = datetime.now(tz=timezone.utc)

    orders: list[Order] = []
    for item in items:
        # Identity first, so a bad email surfaces as an email error rather than
        # being masked by an unrelated pizza error further down the cart.
        member_name = _normalize_member_value(item.member_name, team.member_identifier)
        pizza = pizza_map.get(item.pizza_id)
        if pizza is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Pizza '{item.pizza_id}' not found in menu",
            )
        orders.append(Order(
            id=new_id(),
            session_id=session.id,
            member_name=member_name,
            pizza_id=pizza.id,
            pizza_name=pizza.name,
            pizza_price=pizza.price,
            total_price=pizza.price,
            created_at=created_at,
            client_ip=client_ip,
            comment=item.comment,
        ))

    # All items validated — persist the whole cart in one transaction
    add_orders_to_session(team.id, session.id, orders)
    order_ids = [o.id for o in orders]

    return SubmitOrderResponse(
        status="submitted",
        orders_created=len(order_ids),
        order_ids=order_ids,
    )
