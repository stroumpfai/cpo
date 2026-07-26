import asyncio
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse, StreamingResponse

from models import (
    ChangePasswordRequest,
    CPOResponse,
    CreateMenuRequest,
    CreatePizzaRequest,
    CreateSessionRequest,
    MenuPortable,
    MenuResponse,
    PizzaResponse,
    SessionResponse,
    SetReceivedRequest,
    SummaryResponse,
    UpdateCurrencyRequest,
    UpdateMenuRequest,
    UpdateTeamNameRequest,
    UpdatePizzaRequest,
)
from security import CurrentUser, issue_sse_token, require_cpo, require_cpo_sse
from services import cpo_service, summary_service
from storage import load_session

router = APIRouter(tags=["cpo"])

CPO = Annotated[CurrentUser, Depends(require_cpo)]


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

@router.get("/me", response_model=CPOResponse)
def get_me(user: CPO):
    return cpo_service.get_cpo(user.user_id)


@router.post("/change-password", status_code=204)
def change_password(body: ChangePasswordRequest, user: CPO):
    cpo_service.change_password(user.user_id, body.current_password, body.new_password)


@router.patch("/currency", response_model=CPOResponse)
def update_currency(body: UpdateCurrencyRequest, user: CPO):
    return cpo_service.update_currency(user.user_id, body.currency)


@router.patch("/team-name", response_model=CPOResponse)
def update_team_name(body: UpdateTeamNameRequest, user: CPO):
    return cpo_service.update_team_name(user.user_id, body.team_name)


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

@router.post("/sessions", response_model=SessionResponse, status_code=201)
def create_session(body: CreateSessionRequest, user: CPO):
    cpo = cpo_service.get_cpo(user.user_id)
    return cpo_service.create_session(
        cpo=cpo,
        session_date=body.session_date,
        start_time=body.start_time,
        end_time=body.end_time,
        grace_period_minutes=body.grace_period_minutes,
        menu_id=body.menu_id,
    )


@router.get("/sessions", response_model=list[SessionResponse])
def list_sessions(user: CPO):
    cpo = cpo_service.get_cpo(user.user_id)
    return cpo_service.get_sessions(cpo)


@router.post("/sessions/{session_id}/close", response_model=SessionResponse)
def close_session(session_id: UUID, user: CPO):
    return cpo_service.close_session(user.user_id, str(session_id))


@router.get("/sessions/{session_id}/summary", response_model=SummaryResponse)
def get_summary(session_id: UUID, user: CPO):
    session = cpo_service.get_session_or_404(user.user_id, str(session_id))
    return summary_service.build_summary(session)


@router.post("/sessions/{session_id}/sse-token", status_code=201)
def create_sse_token(session_id: UUID, user: CPO):
    """Issue a short-lived one-time token for the EventSource SSE connection."""
    session = cpo_service.get_session_or_404(user.user_id, str(session_id))
    return {"sse_token": issue_sse_token(user.user_id), "session_id": session.id}


@router.get("/sessions/{session_id}/summary/sse")
async def summary_sse(
    session_id: UUID,
    user: Annotated[CurrentUser, Depends(require_cpo_sse)],
):
    # Verify session exists and belongs to this CPO before opening the stream
    session = await asyncio.to_thread(load_session, user.user_id, str(session_id))
    if session is None:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return StreamingResponse(
        cpo_service.session_sse_events(user.user_id, str(session_id)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Menus
# ---------------------------------------------------------------------------

@router.get("/menus", response_model=list[MenuResponse])
def list_menus(user: CPO):
    return cpo_service.get_menus(user.user_id)


@router.post("/menus", response_model=MenuResponse, status_code=201)
def create_menu(body: CreateMenuRequest, user: CPO):
    return cpo_service.create_menu(user.user_id, body.name, body.pizzeria_url)


@router.patch("/menus/{menu_id}", response_model=MenuResponse)
def update_menu(menu_id: UUID, body: UpdateMenuRequest, user: CPO):
    return cpo_service.update_menu(user.user_id, str(menu_id), body)


@router.delete("/menus/{menu_id}", status_code=204)
def delete_menu(menu_id: UUID, user: CPO):
    cpo_service.delete_menu(user.user_id, str(menu_id))


@router.post("/menus/{menu_id}/default", status_code=204)
def set_default_menu(menu_id: UUID, user: CPO):
    cpo_service.set_default_menu(user.user_id, str(menu_id))


@router.get("/menus/{menu_id}/export")
def export_menu(menu_id: UUID, user: CPO):
    portable = cpo_service.export_menu(user.user_id, str(menu_id))
    return JSONResponse(
        content=portable.model_dump(mode="json"),
        headers={"Content-Disposition": "attachment; filename=\"menu.json\""},
    )


@router.post("/menus/{menu_id}/import", status_code=204)
def import_menu(menu_id: UUID, body: MenuPortable, user: CPO):
    try:
        cpo_service.import_menu(user.user_id, str(menu_id), body)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/menus/{menu_id}/pizzas", response_model=list[PizzaResponse])
def get_menu_pizzas(menu_id: UUID, user: CPO):
    return cpo_service.get_menu_pizzas(user.user_id, str(menu_id))


@router.post("/menus/{menu_id}/pizzas", response_model=PizzaResponse, status_code=201)
def add_pizza(menu_id: UUID, body: CreatePizzaRequest, user: CPO):
    return cpo_service.add_pizza(user.user_id, str(menu_id), body.name, body.price)


@router.put("/menus/{menu_id}/pizzas/{pizza_id}", response_model=PizzaResponse)
def update_pizza(menu_id: UUID, pizza_id: str, body: UpdatePizzaRequest, user: CPO):
    return cpo_service.update_pizza(user.user_id, str(menu_id), pizza_id, body.name, body.price)


@router.delete("/menus/{menu_id}/pizzas/{pizza_id}", status_code=204)
def delete_pizza(menu_id: UUID, pizza_id: str, user: CPO):
    cpo_service.delete_pizza(user.user_id, str(menu_id), pizza_id)


# ---------------------------------------------------------------------------
# Order deletion (CPO action from dashboard)
# ---------------------------------------------------------------------------

@router.delete("/orders/{order_id}", status_code=204)
def delete_order(order_id: str, user: CPO):
    cpo_service.delete_order(user.user_id, order_id)


@router.patch("/orders/{order_id}/received", status_code=204)
def set_order_received(order_id: str, body: SetReceivedRequest, user: CPO):
    cpo_service.set_order_received(user.user_id, order_id, body.received)
