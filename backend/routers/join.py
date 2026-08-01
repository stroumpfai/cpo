"""Public (no auth) invite-link signup — a second CPO joining an existing team."""
from fastapi import APIRouter, Response

from models import JoinInfoResponse, JoinTeamRequest, LoginResponse
from routers.auth import _set_auth_cookie
from security import create_token
from services import team_service

router = APIRouter(tags=["join"])


@router.get("/{token}", response_model=JoinInfoResponse)
def get_invite_info(token: str):
    return JoinInfoResponse(team_name=team_service.get_invite_team_name(token))


@router.post("/{token}", response_model=LoginResponse)
def join_team(token: str, body: JoinTeamRequest, response: Response):
    cpo = team_service.redeem_invite(token, body.username, body.email, body.password)
    token_str = create_token(user_id=cpo.id, role="cpo", version=cpo.token_version)
    _set_auth_cookie(response, token_str)
    return LoginResponse(token=token_str, role="cpo")
