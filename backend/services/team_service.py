"""Team member and invite management (self-service, any team peer).

All CPO logins on a team are equal peers — no owner/deputy hierarchy. Any
member can list/remove teammates, reset a teammate's password, and create or
revoke invite links. The only asymmetric rule is that a team must always keep
at least one login: removing the last member is rejected (mirrors
admin_service.delete_admin's "cannot delete the last admin" guard).
"""
from datetime import datetime, timedelta, timezone

from fastapi import status

from config import TEAM_INVITE_EXPIRY_HOURS
from error_codes import AppError
from models import CPORecord, TeamInvite, TeamMemberResponse, TeamInviteResponse
from password_policy import validate_password
from services.admin_service import username_taken
from storage import (
    create_invite as storage_create_invite,
    delete_invite as storage_delete_invite,
    get_invite_by_token,
    list_invites as storage_list_invites,
    load_config,
    mark_invite_used,
    save_config,
)
from utils import generate_link, hash_password, new_id

_MEMBER_NOT_FOUND = "Team member not found"
_INVITE_NOT_FOUND = "Invite not found"


def _team_members(cfg, team_id: str) -> list[CPORecord]:
    return [c for c in cfg.cpos if c.team_id == team_id]


def list_team_members(team_id: str, actor_cpo_id: str) -> list[TeamMemberResponse]:
    return [
        TeamMemberResponse(
            id=c.id, username=c.username, email=c.email,
            created_at=c.created_at, is_self=c.id == actor_cpo_id,
        )
        for c in _team_members(load_config(), team_id)
    ]


def remove_team_member(team_id: str, member_id: str) -> None:
    cfg = load_config()
    members = _team_members(cfg, team_id)
    target = next((c for c in members if c.id == member_id), None)
    if target is None:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="team_member_not_found",
            message=_MEMBER_NOT_FOUND,
        )
    if len(members) <= 1:
        raise AppError(
            status_code=status.HTTP_409_CONFLICT,
            code="last_team_member",
            message="Cannot remove the last member of a team",
        )
    cfg.cpos = [c for c in cfg.cpos if c.id != member_id]
    save_config(cfg)


def reset_teammate_password(team_id: str, member_id: str, new_password: str) -> TeamMemberResponse:
    cfg = load_config()
    target = next((c for c in _team_members(cfg, team_id) if c.id == member_id), None)
    if target is None:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="team_member_not_found",
            message=_MEMBER_NOT_FOUND,
        )
    validate_password(new_password, target.username)
    target.password_hash = hash_password(new_password)
    target.token_version += 1
    save_config(cfg)
    return TeamMemberResponse(
        id=target.id, username=target.username, email=target.email,
        created_at=target.created_at,
    )


# ---------------------------------------------------------------------------
# Invite links
# ---------------------------------------------------------------------------

def list_pending_invites(team_id: str) -> list[TeamInviteResponse]:
    now = datetime.now(tz=timezone.utc)
    return [
        TeamInviteResponse(id=i.id, token=i.token, created_at=i.created_at, expires_at=i.expires_at)
        for i in storage_list_invites(team_id)
        if i.used_at is None and i.expires_at > now
    ]


def create_invite(team_id: str, created_by_cpo_id: str) -> TeamInviteResponse:
    now = datetime.now(tz=timezone.utc)
    invite = TeamInvite(
        id=new_id(),
        team_id=team_id,
        token=generate_link(),
        created_by_cpo_id=created_by_cpo_id,
        created_at=now,
        expires_at=now + timedelta(hours=TEAM_INVITE_EXPIRY_HOURS),
    )
    storage_create_invite(invite)
    return TeamInviteResponse(
        id=invite.id, token=invite.token, created_at=invite.created_at, expires_at=invite.expires_at
    )


def revoke_invite(team_id: str, invite_id: str) -> None:
    if not storage_delete_invite(team_id, invite_id):
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="invite_not_found",
            message=_INVITE_NOT_FOUND,
        )


def _valid_invite_or_404(token: str) -> TeamInvite:
    invite = get_invite_by_token(token)
    if invite is None or invite.used_at is not None or invite.expires_at <= datetime.now(tz=timezone.utc):
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="invite_invalid",
            message="Invite link not found or expired",
        )
    return invite


def get_invite_team_name(token: str) -> str:
    invite = _valid_invite_or_404(token)
    cfg = load_config()
    team = next((t for t in cfg.teams if t.id == invite.team_id), None)
    if team is None:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="invite_invalid",
            message="Invite link not found or expired",
        )
    return team.team_name


def redeem_invite(token: str, username: str, email: str, password: str) -> CPORecord:
    invite = _valid_invite_or_404(token)
    cfg = load_config()

    if username_taken(cfg, username):
        raise AppError(
            status_code=status.HTTP_409_CONFLICT,
            code="username_exists",
            message="Username already exists",
        )
    if any(c.email.lower() == email.lower() for c in cfg.cpos):
        raise AppError(
            status_code=status.HTTP_409_CONFLICT,
            code="email_exists",
            message="Email already exists",
        )
    validate_password(password, username)

    # Single-use, race-safe: the UPDATE only succeeds if used_at is still NULL.
    if not mark_invite_used(invite.id, datetime.now(tz=timezone.utc).isoformat()):
        raise AppError(
            status_code=status.HTTP_409_CONFLICT,
            code="invite_used",
            message="Invite link already used",
        )

    cpo = CPORecord(
        id=new_id(),
        team_id=invite.team_id,
        username=username,
        email=email,
        password_hash=hash_password(password),
        created_at=datetime.now(tz=timezone.utc),
    )
    cfg.cpos.append(cpo)
    save_config(cfg)
    return cpo
