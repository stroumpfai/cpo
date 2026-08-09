import asyncio
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse, StreamingResponse

from error_codes import AppError
from models import (
    ChangePasswordRequest,
    CPOResponse,
    CPOStatsResponse,
    CreateMenuRequest,
    CreatePizzaRequest,
    CreateSessionRequest,
    MenuPortable,
    MenuResponse,
    PizzaResponse,
    ResetPasswordRequest,
    SessionResponse,
    SetReceivedRequest,
    SummaryResponse,
    TeamInviteResponse,
    TeamMemberResponse,
    UpdateCurrencyRequest,
    UpdateLanguageRequest,
    UpdateMemberIdentifierRequest,
    UpdateMenuRequest,
    UpdateTeamNameRequest,
    UpdatePizzaRequest,
)
from security import CurrentUser, issue_sse_token, require_cpo, require_cpo_sse
from services import cpo_service, stats_service, summary_service, team_service
from storage import load_session

router = APIRouter(tags=["cpo"])

CPO = Annotated[CurrentUser, Depends(require_cpo)]


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

@router.get("/me", response_model=CPOResponse)
def get_me(user: CPO):
    return cpo_service.get_profile(user.user_id)


@router.post("/change-password", status_code=204)
def change_password(body: ChangePasswordRequest, user: CPO):
    cpo_service.change_password(user.user_id, body.current_password, body.new_password)


@router.patch("/currency", response_model=CPOResponse)
def update_currency(body: UpdateCurrencyRequest, user: CPO):
    cpo_service.update_currency(user.team_id, body.currency)
    return cpo_service.get_profile(user.user_id)


@router.patch("/team-name", response_model=CPOResponse)
def update_team_name(body: UpdateTeamNameRequest, user: CPO):
    cpo_service.update_team_name(user.team_id, body.team_name)
    return cpo_service.get_profile(user.user_id)


@router.patch("/member-identifier", response_model=CPOResponse)
def update_member_identifier(body: UpdateMemberIdentifierRequest, user: CPO):
    cpo_service.update_member_identifier(user.team_id, body.member_identifier)
    return cpo_service.get_profile(user.user_id)


@router.patch("/language", response_model=CPOResponse)
def update_language(body: UpdateLanguageRequest, user: CPO):
    # user_id, not team_id: language is a per-login preference.
    cpo_service.update_language(user.user_id, body.language)
    return cpo_service.get_profile(user.user_id)


# ---------------------------------------------------------------------------
# Team members & invites (self-service — any team peer)
# ---------------------------------------------------------------------------

@router.get("/team-members", response_model=list[TeamMemberResponse])
def list_team_members(user: CPO):
    return team_service.list_team_members(user.team_id, user.user_id)


@router.delete("/team-members/{member_id}", status_code=204)
def remove_team_member(member_id: str, user: CPO):
    team_service.remove_team_member(user.team_id, member_id)


@router.post("/team-members/{member_id}/reset-password", response_model=TeamMemberResponse)
def reset_teammate_password(member_id: str, body: ResetPasswordRequest, user: CPO):
    return team_service.reset_teammate_password(user.team_id, member_id, body.new_password)


@router.get("/team-invites", response_model=list[TeamInviteResponse])
def list_team_invites(user: CPO):
    return team_service.list_pending_invites(user.team_id)


@router.post("/team-invites", response_model=TeamInviteResponse, status_code=201)
def create_team_invite(user: CPO):
    return team_service.create_invite(user.team_id, user.user_id)


@router.delete("/team-invites/{invite_id}", status_code=204)
def revoke_team_invite(invite_id: str, user: CPO):
    team_service.revoke_invite(user.team_id, invite_id)


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

@router.post("/sessions", response_model=SessionResponse, status_code=201)
def create_session(body: CreateSessionRequest, user: CPO):
    team = cpo_service.get_team(user.team_id)
    return cpo_service.create_session(
        team=team,
        session_date=body.session_date,
        start_time=body.start_time,
        end_time=body.end_time,
        grace_period_minutes=body.grace_period_minutes,
        menu_id=body.menu_id,
    )


@router.get("/sessions", response_model=list[SessionResponse])
def list_sessions(user: CPO):
    team = cpo_service.get_team(user.team_id)
    return cpo_service.get_sessions(team)


@router.post("/sessions/{session_id}/close", response_model=SessionResponse)
def close_session(session_id: UUID, user: CPO):
    return cpo_service.close_session(user.team_id, str(session_id))


@router.get("/sessions/{session_id}/summary", response_model=SummaryResponse)
def get_summary(session_id: UUID, user: CPO):
    session = cpo_service.get_session_or_404(user.team_id, str(session_id))
    return summary_service.build_summary(session)


@router.post("/sessions/{session_id}/sse-token", status_code=201)
def create_sse_token(session_id: UUID, user: CPO):
    """Issue a short-lived one-time token for the EventSource SSE connection."""
    session = cpo_service.get_session_or_404(user.team_id, str(session_id))
    return {"sse_token": issue_sse_token(user.user_id), "session_id": session.id}


@router.get("/sessions/{session_id}/summary/sse")
async def summary_sse(
    session_id: UUID,
    user: Annotated[CurrentUser, Depends(require_cpo_sse)],
):
    # Verify session exists and belongs to this team before opening the stream
    session = await asyncio.to_thread(load_session, user.team_id, str(session_id))
    if session is None:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="session_not_found",
            message="Session not found",
        )
    return StreamingResponse(
        cpo_service.session_sse_events(user.team_id, str(session_id)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

@router.get("/stats", response_model=CPOStatsResponse)
def get_stats(user: CPO):
    return stats_service.get_stats(user.team_id)


@router.post("/stats/reset", response_model=CPOStatsResponse)
def reset_stats(user: CPO):
    return stats_service.reset_stats(user.team_id)


# ---------------------------------------------------------------------------
# Menus
# ---------------------------------------------------------------------------

@router.get("/menus", response_model=list[MenuResponse])
def list_menus(user: CPO):
    return cpo_service.get_menus(user.team_id)


@router.post("/menus", response_model=MenuResponse, status_code=201)
def create_menu(body: CreateMenuRequest, user: CPO):
    return cpo_service.create_menu(user.team_id, body.name, body.pizzeria_url)


@router.patch("/menus/{menu_id}", response_model=MenuResponse)
def update_menu(menu_id: UUID, body: UpdateMenuRequest, user: CPO):
    return cpo_service.update_menu(user.team_id, str(menu_id), body)


@router.delete("/menus/{menu_id}", status_code=204)
def delete_menu(menu_id: UUID, user: CPO):
    cpo_service.delete_menu(user.team_id, str(menu_id))


@router.post("/menus/{menu_id}/default", status_code=204)
def set_default_menu(menu_id: UUID, user: CPO):
    cpo_service.set_default_menu(user.team_id, str(menu_id))


@router.get("/menus/{menu_id}/export")
def export_menu(menu_id: UUID, user: CPO):
    portable = cpo_service.export_menu(user.team_id, str(menu_id))
    return JSONResponse(
        content=portable.model_dump(mode="json"),
        headers={"Content-Disposition": "attachment; filename=\"menu.json\""},
    )


@router.post("/menus/{menu_id}/import", status_code=204)
def import_menu(menu_id: UUID, body: MenuPortable, user: CPO):
    # import_menu raises AppError("menu_import_duplicate_name") itself — it is the
    # only layer that knows which dish collided, and the code keeps the message
    # translatable instead of shipping the reason as English prose.
    cpo_service.import_menu(user.team_id, str(menu_id), body)


@router.get("/menus/{menu_id}/pizzas", response_model=list[PizzaResponse])
def get_menu_pizzas(menu_id: UUID, user: CPO):
    return cpo_service.get_menu_pizzas(user.team_id, str(menu_id))


@router.post("/menus/{menu_id}/pizzas", response_model=PizzaResponse, status_code=201)
def add_pizza(menu_id: UUID, body: CreatePizzaRequest, user: CPO):
    return cpo_service.add_pizza(user.team_id, str(menu_id), body.name, body.price)


@router.put("/menus/{menu_id}/pizzas/{pizza_id}", response_model=PizzaResponse)
def update_pizza(menu_id: UUID, pizza_id: str, body: UpdatePizzaRequest, user: CPO):
    return cpo_service.update_pizza(user.team_id, str(menu_id), pizza_id, body.name, body.price)


@router.delete("/menus/{menu_id}/pizzas/{pizza_id}", status_code=204)
def delete_pizza(menu_id: UUID, pizza_id: str, user: CPO):
    cpo_service.delete_pizza(user.team_id, str(menu_id), pizza_id)


# ---------------------------------------------------------------------------
# Order deletion (CPO action from dashboard)
# ---------------------------------------------------------------------------

@router.delete("/orders/{order_id}", status_code=204)
def delete_order(order_id: str, user: CPO):
    cpo_service.delete_order(user.team_id, order_id)


@router.patch("/orders/{order_id}/received", status_code=204)
def set_order_received(order_id: str, body: SetReceivedRequest, user: CPO):
    cpo_service.set_order_received(user.team_id, order_id, body.received)
