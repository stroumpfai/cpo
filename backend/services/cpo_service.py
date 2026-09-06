import asyncio
import json
from datetime import date, timezone, datetime
from typing import AsyncGenerator

from fastapi import status

from error_codes import AppError
from models import (
    CPOResponse,
    CPORecord,
    Menu,
    MenuPortable,
    MenuResponse,
    Pizza,
    PortablePizzaItem,
    SessionFile,
    TeamRecord,
    UpdateMenuRequest,
)
from password_policy import validate_password
from storage import (
    create_menu as storage_create_menu,
    delete_menu as storage_delete_menu,
    delete_order_for_cpo,
    get_default_menu,
    get_menu,
    list_menus,
    list_sessions,
    load_config,
    load_session,
    save_config,
    save_menu,
    save_session,
    set_default_menu as storage_set_default_menu,
    set_order_received_for_cpo,
    update_cpo_fields,
    update_team_fields,
)
from utils import compute_session_status, hash_password, new_id, verify_password

_MENU_NOT_FOUND = "Menu not found"
_TEAM_NOT_FOUND = "Team not found"


# ---------------------------------------------------------------------------
# CPO profile
# ---------------------------------------------------------------------------

def _find_cpo(cfg, cpo_id: str) -> CPORecord:
    cpo = next((c for c in cfg.cpos if c.id == cpo_id), None)
    if cpo is None:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="cpo_not_found",
            message="CPO not found",
        )
    return cpo


def _find_team(cfg, team_id: str) -> TeamRecord:
    team = next((t for t in cfg.teams if t.id == team_id), None)
    if team is None:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="team_not_found",
            message=_TEAM_NOT_FOUND,
        )
    return team


def get_cpo(cpo_id: str) -> CPORecord:
    return _find_cpo(load_config(), cpo_id)


def get_team(team_id: str) -> TeamRecord:
    return _find_team(load_config(), team_id)


def get_profile(cpo_id: str) -> CPOResponse:
    """The logged-in CPO's own login joined with their team's settings."""
    cfg = load_config()
    cpo = _find_cpo(cfg, cpo_id)
    team = _find_team(cfg, cpo.team_id)
    return CPOResponse(
        id=cpo.id,
        username=cpo.username,
        email=cpo.email,
        team_id=team.id,
        team_name=team.team_name,
        unique_link=team.unique_link,
        created_at=cpo.created_at,
        currency=team.currency,
        member_identifier=team.member_identifier,
        default_grace_period_minutes=team.default_grace_period_minutes,
        language=cpo.language,
    )


def _update_team_setting(team_id: str, **fields) -> TeamRecord:
    """Persist one settings field via a targeted UPDATE.

    The settings page saves its fields in parallel, so these must not
    read-modify-write the whole config — see storage.update_team_fields.
    """
    team = update_team_fields(team_id, **fields)
    if team is None:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="team_not_found",
            message=_TEAM_NOT_FOUND,
        )
    return team


def update_team_name(team_id: str, team_name: str) -> TeamRecord:
    return _update_team_setting(team_id, team_name=team_name.strip())


def update_currency(team_id: str, currency: str) -> TeamRecord:
    return _update_team_setting(team_id, currency=currency.strip())


def update_member_identifier(team_id: str, member_identifier: str) -> TeamRecord:
    return _update_team_setting(team_id, member_identifier=member_identifier)


def update_default_grace_period(team_id: str, minutes: int) -> TeamRecord:
    return _update_team_setting(team_id, default_grace_period_minutes=minutes)


def update_language(cpo_id: str, language: str | None) -> CPORecord:
    """Set this login's UI language. Keyed on the login id, not the team id:
    unlike the settings above, language is personal — teammates sharing a team
    each pick their own. None clears it back to "follow the browser"."""
    cpo = update_cpo_fields(cpo_id, language=language)
    if cpo is None:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="cpo_not_found",
            message="CPO not found",
        )
    return cpo


def change_password(cpo_id: str, current_password: str, new_password: str) -> None:
    cfg = load_config()
    cpo = _find_cpo(cfg, cpo_id)
    if not verify_password(current_password, cpo.password_hash):
        raise AppError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="current_password_incorrect",
            message="Current password is incorrect.",
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
        "team_id": session.team_id,
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
        "menu_id": session.menu_id,
    }


def _resolve_session_menu(team_id: str, menu_id: str | None) -> Menu:
    """Menu a new session will serve: the requested one, or the team's default."""
    if menu_id is not None:
        menu = get_menu(team_id, menu_id)
        if menu is None:
            raise AppError(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                code="menu_not_found",
                message=_MENU_NOT_FOUND,
            )
        return menu
    menu = get_default_menu(team_id)
    if menu is None:
        raise AppError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="no_menus",
            message="Create a menu before opening a session.",
        )
    return menu


def create_session(
    team: TeamRecord,
    session_date: date,
    start_time: str,
    end_time: str,
    grace_period_minutes: int,
    menu_id: str | None = None,
) -> dict:
    # Session times are combined with session_date as a single calendar day
    # (see utils.session_datetime) — end_time <= start_time would place the
    # close instant before the session even opens, so the session would flip
    # straight from "upcoming" to "closed" the moment start_time arrives and
    # never accept an order. Reject rather than let that happen silently.
    if end_time <= start_time:
        raise AppError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="end_before_start",
            message="End time must be after start time. Sessions spanning midnight are not supported yet.",
        )

    # Reject sessions whose close time has already passed — they would be
    # created as "closed" and never accept any orders.
    if compute_session_status(session_date, start_time, end_time, grace_period_minutes) == "closed":
        raise AppError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="session_end_passed",
            message="Session end time has already passed. Please set a future end time.",
        )

    menu = _resolve_session_menu(team.id, menu_id)

    for s in list_sessions(team.id):
        st = compute_session_status(s.session_date, s.start_time, s.end_time, s.grace_period_minutes, s.closed_at)
        if st in ("upcoming", "active"):
            raise AppError(
                status_code=status.HTTP_409_CONFLICT,
                code="session_already_open",
                message="Team already has an active or upcoming session",
            )

    session = SessionFile(
        id=new_id(),
        team_id=team.id,
        team_name=team.team_name,
        session_date=session_date,
        start_time=start_time,
        end_time=end_time,
        grace_period_minutes=grace_period_minutes,
        created_at=datetime.now(tz=timezone.utc),
        menu_id=menu.id,
    )
    save_session(session)
    return _session_to_dict(session, team.unique_link)


def get_sessions(team: TeamRecord) -> list[dict]:
    return [_session_to_dict(s, team.unique_link) for s in list_sessions(team.id)]


def get_session_or_404(team_id: str, session_id: str) -> SessionFile:
    session = load_session(team_id, session_id)
    if session is None:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="session_not_found",
            message="Session not found",
        )
    return session


# ---------------------------------------------------------------------------
# Menus
# ---------------------------------------------------------------------------

def _menu_to_response(menu: Menu) -> MenuResponse:
    return MenuResponse(
        id=menu.id,
        name=menu.name,
        is_default=menu.is_default,
        pizzeria_url=menu.pizzeria_url,
        pizza_count=len(menu.pizzas),
    )


def get_menu_or_404(team_id: str, menu_id: str) -> Menu:
    menu = get_menu(team_id, menu_id)
    if menu is None:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="menu_not_found",
            message=_MENU_NOT_FOUND,
        )
    return menu


def _check_menu_name(team_id: str, name: str, exclude_id: str | None = None) -> str:
    name = name.strip()
    if not name:
        raise AppError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="menu_name_required",
            message="Menu name is required",
        )
    for m in list_menus(team_id):
        if m.name.lower() == name.lower() and m.id != exclude_id:
            raise AppError(
                status_code=status.HTTP_409_CONFLICT,
                code="menu_name_exists",
                message="Menu name already exists",
            )
    return name


def get_menus(team_id: str) -> list[MenuResponse]:
    return [_menu_to_response(m) for m in list_menus(team_id)]


def create_menu(team_id: str, name: str, pizzeria_url: str | None = None) -> MenuResponse:
    name = _check_menu_name(team_id, name)
    menu = storage_create_menu(team_id, name, pizzeria_url)
    return _menu_to_response(menu)


def update_menu(team_id: str, menu_id: str, body: UpdateMenuRequest) -> MenuResponse:
    menu = get_menu_or_404(team_id, menu_id)
    if body.name is not None:
        menu.name = _check_menu_name(team_id, body.name, exclude_id=menu_id)
    # Omitted field keeps the current url; explicit null clears it.
    if "pizzeria_url" in body.model_fields_set:
        menu.pizzeria_url = body.pizzeria_url
    save_menu(menu)
    return _menu_to_response(menu)


def delete_menu(team_id: str, menu_id: str) -> None:
    get_menu_or_404(team_id, menu_id)
    for s in list_sessions(team_id):
        if s.menu_id != menu_id:
            continue
        st = compute_session_status(
            s.session_date, s.start_time, s.end_time,
            s.grace_period_minutes, s.closed_at,
        )
        if st in ("upcoming", "active"):
            raise AppError(
                status_code=status.HTTP_409_CONFLICT,
                code="menu_in_use",
                message="Menu is used by an active or upcoming session",
            )
    storage_delete_menu(team_id, menu_id)


def set_default_menu(team_id: str, menu_id: str) -> None:
    if not storage_set_default_menu(team_id, menu_id):
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="menu_not_found",
            message=_MENU_NOT_FOUND,
        )


def get_menu_pizzas(team_id: str, menu_id: str) -> list[Pizza]:
    return get_menu_or_404(team_id, menu_id).pizzas


def add_pizza(team_id: str, menu_id: str, name: str, price: float) -> Pizza:
    menu = get_menu_or_404(team_id, menu_id)
    if any(p.name.lower() == name.lower() for p in menu.pizzas):
        raise AppError(
            status_code=status.HTTP_409_CONFLICT,
            code="pizza_name_exists",
            message="Pizza name already exists",
        )
    pizza = Pizza(id=new_id(), name=name, price=price)
    menu.pizzas.append(pizza)
    save_menu(menu)
    return pizza


def update_pizza(team_id: str, menu_id: str, pizza_id: str, name: str, price: float) -> Pizza:
    menu = get_menu_or_404(team_id, menu_id)
    pizza = next((p for p in menu.pizzas if p.id == pizza_id), None)
    if pizza is None:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="pizza_not_found",
            message="Pizza not found",
        )
    if any(p.name.lower() == name.lower() and p.id != pizza_id for p in menu.pizzas):
        raise AppError(
            status_code=status.HTTP_409_CONFLICT,
            code="pizza_name_exists",
            message="Pizza name already exists",
        )
    pizza.name = name
    pizza.price = price
    save_menu(menu)
    return pizza


def delete_pizza(team_id: str, menu_id: str, pizza_id: str) -> None:
    menu = get_menu_or_404(team_id, menu_id)
    before = len(menu.pizzas)
    menu.pizzas = [p for p in menu.pizzas if p.id != pizza_id]
    if len(menu.pizzas) == before:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="pizza_not_found",
            message="Pizza not found",
        )
    save_menu(menu)


def export_menu(team_id: str, menu_id: str) -> MenuPortable:
    menu = get_menu_or_404(team_id, menu_id)
    return MenuPortable(
        dishes=[PortablePizzaItem(name=p.name, price=p.price) for p in menu.pizzas],
        url=menu.pizzeria_url,
    )


def import_menu(team_id: str, menu_id: str, portable: MenuPortable) -> None:
    """Replace the menu's items and url with the imported file's content."""
    seen: set[str] = set()
    for item in portable.dishes:
        key = item.name.lower()
        if key in seen:
            raise AppError(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                code="menu_import_duplicate_name",
                message=f"Duplicate dish name in import: '{item.name}'",
                params={"name": item.name},
            )
        seen.add(key)
    menu = get_menu_or_404(team_id, menu_id)
    menu.pizzas = [
        Pizza(id=new_id(), name=item.name, price=item.price) for item in portable.dishes
    ]
    menu.pizzeria_url = portable.url
    save_menu(menu)


# ---------------------------------------------------------------------------
# Order deletion (CPO action)
# ---------------------------------------------------------------------------

def delete_order(team_id: str, order_id: str) -> None:
    if not delete_order_for_cpo(team_id, order_id):
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="order_not_found",
            message="Order not found",
        )


def set_order_received(team_id: str, order_id: str, received: bool) -> None:
    if not set_order_received_for_cpo(team_id, order_id, received):
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="order_not_found",
            message="Order not found",
        )


# ---------------------------------------------------------------------------
# Force-close session
# ---------------------------------------------------------------------------

def close_session(team_id: str, session_id: str) -> dict:
    session = load_session(team_id, session_id)
    if session is None:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="session_not_found",
            message="Session not found",
        )

    current_status = compute_session_status(
        session.session_date, session.start_time, session.end_time,
        session.grace_period_minutes, session.closed_at,
    )
    if current_status == "closed":
        raise AppError(
            status_code=status.HTTP_409_CONFLICT,
            code="session_already_closed",
            message="Session is already closed",
        )

    session.closed_at = datetime.now(tz=timezone.utc)
    save_session(session)

    team = get_team(team_id)
    return _session_to_dict(session, team.unique_link)


# ---------------------------------------------------------------------------
# SSE streaming
# ---------------------------------------------------------------------------

async def session_sse_events(team_id: str, session_id: str) -> AsyncGenerator[str, None]:
    """
    Async generator that yields SSE-formatted strings.

    Polls the session file every second and emits an "update" event whenever
    the order count or status changes.  Terminates (and emits "session_closed")
    once the session is past its grace period.
    """
    from services.summary_service import build_summary

    last_hash: str | None = None

    while True:
        session = await asyncio.to_thread(load_session, team_id, session_id)
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
