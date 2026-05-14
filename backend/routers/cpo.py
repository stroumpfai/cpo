import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from models import (
    CPOResponse,
    CreatePizzaRequest,
    CreateSessionRequest,
    PizzaResponse,
    SessionResponse,
    SummaryResponse,
    UpdatePizzaRequest,
)
from security import CurrentUser, require_cpo, require_cpo_sse
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
    )


@router.get("/sessions", response_model=list[SessionResponse])
def list_sessions(user: CPO):
    cpo = cpo_service.get_cpo(user.user_id)
    return cpo_service.get_sessions(cpo)


@router.get("/sessions/{session_id}/summary", response_model=SummaryResponse)
def get_summary(session_id: str, user: CPO):
    session = cpo_service.get_session_or_404(user.user_id, session_id)
    return summary_service.build_summary(session)


@router.get("/sessions/{session_id}/summary/sse")
async def summary_sse(
    session_id: str,
    user: Annotated[CurrentUser, Depends(require_cpo_sse)],
):
    # Verify session exists and belongs to this CPO before opening the stream
    session = await asyncio.to_thread(load_session, user.user_id, session_id)
    if session is None:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return StreamingResponse(
        cpo_service.session_sse_events(user.user_id, session_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Menu
# ---------------------------------------------------------------------------

@router.get("/menu", response_model=list[PizzaResponse])
def get_menu(user: CPO):
    return cpo_service.get_menu_pizzas(user.user_id)


@router.post("/menu", response_model=PizzaResponse, status_code=201)
def add_pizza(body: CreatePizzaRequest, user: CPO):
    return cpo_service.add_pizza(user.user_id, body.name, body.price)


@router.put("/menu/{pizza_id}", response_model=PizzaResponse)
def update_pizza(pizza_id: str, body: UpdatePizzaRequest, user: CPO):
    return cpo_service.update_pizza(user.user_id, pizza_id, body.name, body.price)


@router.delete("/menu/{pizza_id}", status_code=204)
def delete_pizza(pizza_id: str, user: CPO):
    cpo_service.delete_pizza(user.user_id, pizza_id)


# ---------------------------------------------------------------------------
# Order deletion (CPO action from dashboard)
# ---------------------------------------------------------------------------

@router.delete("/orders/{order_id}", status_code=204)
def delete_order(order_id: str, user: CPO):
    cpo_service.delete_order(user.user_id, order_id)
