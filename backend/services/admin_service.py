from collections import defaultdict
from datetime import timezone, datetime

from fastapi import status

from error_codes import AppError
from models import (
    AdminProfileResponse,
    AdminRecord,
    AdminTeamResponse,
    CPORecord,
    CPOUsageStats,
    SessionUsageItem,
    TeamMemberResponse,
    TeamRecord,
)
from password_policy import validate_password
from storage import delete_admin as storage_delete_admin
from storage import insert_admin, list_session_stats, load_config, save_config, update_admin_fields
from utils import compute_session_status, generate_link, hash_password, new_id, verify_password

_NOT_FOUND = "CPO not found"
_TEAM_NOT_FOUND = "Team not found"
_ADMIN_NOT_FOUND = "Admin not found"
_USERNAME_EXISTS = "Username already exists"


def username_taken(cfg, username: str) -> bool:
    """Case-insensitive check across both roles — login resolves admins first,
    so a cross-role duplicate would shadow the CPO account."""
    lowered = username.lower()
    return any(a.username.lower() == lowered for a in cfg.admins) or any(
        c.username.lower() == lowered for c in cfg.cpos
    )


def _team_to_response(team: TeamRecord, members: list[CPORecord]) -> AdminTeamResponse:
    return AdminTeamResponse(
        team_id=team.id,
        team_name=team.team_name,
        unique_link=team.unique_link,
        currency=team.currency,
        member_identifier=team.member_identifier,
        created_at=team.created_at,
        members=[
            TeamMemberResponse(id=c.id, username=c.username, email=c.email, created_at=c.created_at)
            for c in members
        ],
    )


def list_cpos() -> list[AdminTeamResponse]:
    cfg = load_config()
    members_by_team: dict[str, list[CPORecord]] = defaultdict(list)
    for cpo in cfg.cpos:
        members_by_team[cpo.team_id].append(cpo)
    return [_team_to_response(team, members_by_team.get(team.id, [])) for team in cfg.teams]


def usage_stats() -> list[CPOUsageStats]:
    """Per-team usage stats: past (closed) session count, total orders, latest 3."""
    closed_by_team: dict[str, list] = defaultdict(list)
    for row in list_session_stats():
        status_ = compute_session_status(
            row.session_date, row.start_time, row.end_time,
            row.grace_period_minutes, row.closed_at,
        )
        if status_ == "closed":
            closed_by_team[row.team_id].append(row)

    stats = []
    for team in load_config().teams:
        closed = sorted(
            closed_by_team.get(team.id, []),
            key=lambda r: (r.session_date, r.start_time, r.created_at),
            reverse=True,
        )
        stats.append(CPOUsageStats(
            team_id=team.id,
            team_name=team.team_name,
            past_session_count=len(closed),
            total_orders=sum(r.order_count for r in closed),
            latest_sessions=[
                SessionUsageItem(
                    session_id=r.id,
                    session_date=r.session_date,
                    start_time=r.start_time,
                    end_time=r.end_time,
                    order_count=r.order_count,
                )
                for r in closed[:3]
            ],
        ))
    return stats


def create_cpo(username: str, email: str, team_name: str, initial_password: str) -> AdminTeamResponse:
    """Create a new team plus its first CPO login."""
    cfg = load_config()

    if username_taken(cfg, username):
        raise AppError(
            status_code=status.HTTP_409_CONFLICT,
            code="username_exists",
            message=_USERNAME_EXISTS,
        )
    if any(c.email.lower() == email.lower() for c in cfg.cpos):
        raise AppError(
            status_code=status.HTTP_409_CONFLICT,
            code="email_exists",
            message="Email already exists",
        )

    validate_password(initial_password, username)

    existing_links = {t.unique_link for t in cfg.teams}
    link = generate_link()
    while link in existing_links:
        link = generate_link()

    now = datetime.now(tz=timezone.utc)
    team = TeamRecord(id=new_id(), team_name=team_name, unique_link=link, created_at=now)
    cpo = CPORecord(
        id=new_id(),
        team_id=team.id,
        username=username,
        email=email,
        password_hash=hash_password(initial_password),
        created_at=now,
    )
    cfg.teams.append(team)
    cfg.cpos.append(cpo)
    save_config(cfg)
    return _team_to_response(team, [cpo])


def update_cpo_email(cpo_id: str, email: str) -> TeamMemberResponse:
    cfg = load_config()
    cpo = next((c for c in cfg.cpos if c.id == cpo_id), None)
    if cpo is None:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="cpo_not_found",
            message=_NOT_FOUND,
        )
    if any(c.email.lower() == email.lower() and c.id != cpo_id for c in cfg.cpos):
        raise AppError(
            status_code=status.HTTP_409_CONFLICT,
            code="email_exists",
            message="Email already exists",
        )
    cpo.email = email
    save_config(cfg)
    return TeamMemberResponse(id=cpo.id, username=cpo.username, email=cpo.email, created_at=cpo.created_at)


def update_team_name(team_id: str, team_name: str) -> AdminTeamResponse:
    cfg = load_config()
    team = next((t for t in cfg.teams if t.id == team_id), None)
    if team is None:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="team_not_found",
            message=_TEAM_NOT_FOUND,
        )
    team.team_name = team_name
    save_config(cfg)
    members = [c for c in cfg.cpos if c.team_id == team_id]
    return _team_to_response(team, members)


def delete_cpo(cpo_id: str) -> None:
    """Delete a single CPO login. Deleting a team's last login deletes the
    whole team (menus/sessions/orders cascade) — same as the old single-CPO
    behavior; deleting one of several logins just removes that login."""
    cfg = load_config()
    cpo = next((c for c in cfg.cpos if c.id == cpo_id), None)
    if cpo is None:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="cpo_not_found",
            message=_NOT_FOUND,
        )
    cfg.cpos = [c for c in cfg.cpos if c.id != cpo_id]
    if not any(c.team_id == cpo.team_id for c in cfg.cpos):
        cfg.teams = [t for t in cfg.teams if t.id != cpo.team_id]
    save_config(cfg)


def reset_password(cpo_id: str, new_password: str) -> TeamMemberResponse:
    cfg = load_config()
    cpo = next((c for c in cfg.cpos if c.id == cpo_id), None)
    if cpo is None:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="cpo_not_found",
            message=_NOT_FOUND,
        )
    validate_password(new_password, cpo.username)
    cpo.password_hash = hash_password(new_password)
    cpo.token_version += 1
    save_config(cfg)
    return TeamMemberResponse(id=cpo.id, username=cpo.username, email=cpo.email, created_at=cpo.created_at)


# ---------------------------------------------------------------------------
# Admin account management
# ---------------------------------------------------------------------------

def _find_admin(cfg, admin_id: int) -> AdminRecord:
    admin = next((a for a in cfg.admins if a.id == admin_id), None)
    if admin is None:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="admin_not_found",
            message=_ADMIN_NOT_FOUND,
        )
    return admin


def _admin_to_profile(admin: AdminRecord) -> AdminProfileResponse:
    return AdminProfileResponse(id=admin.id, username=admin.username, language=admin.language)


def get_profile(admin_id: int) -> AdminProfileResponse:
    """The logged-in admin's own account — currently just their UI language."""
    return _admin_to_profile(_find_admin(load_config(), admin_id))


def update_language(admin_id: int, language: str | None) -> AdminProfileResponse:
    """Set this admin's UI language; None clears it back to "follow the browser"."""
    admin = update_admin_fields(admin_id, language=language)
    if admin is None:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="admin_not_found",
            message=_ADMIN_NOT_FOUND,
        )
    return _admin_to_profile(admin)


def list_admins(actor_id: int) -> list[dict]:
    return [
        {
            "id": a.id,
            "username": a.username,
            "created_at": a.created_at,
            "is_self": a.id == actor_id,
        }
        for a in load_config().admins
    ]


def create_admin(username: str, initial_password: str) -> AdminRecord:
    cfg = load_config()
    if username_taken(cfg, username):
        raise AppError(
            status_code=status.HTTP_409_CONFLICT,
            code="username_exists",
            message=_USERNAME_EXISTS,
        )
    validate_password(initial_password, username)
    return insert_admin(
        username=username,
        password_hash=hash_password(initial_password),
        created_at=datetime.now(tz=timezone.utc).isoformat(),
    )


def delete_admin(actor_id: int, admin_id: int) -> None:
    cfg = load_config()
    _find_admin(cfg, admin_id)
    if admin_id == actor_id:
        raise AppError(
            status_code=status.HTTP_403_FORBIDDEN,
            code="cannot_delete_self",
            message="You cannot delete your own account",
        )
    if len(cfg.admins) <= 1:
        raise AppError(
            status_code=status.HTTP_409_CONFLICT,
            code="last_admin",
            message="Cannot delete the last admin account",
        )
    storage_delete_admin(admin_id)


def reset_admin_password(actor_id: int, admin_id: int, new_password: str) -> AdminRecord:
    cfg = load_config()
    admin = _find_admin(cfg, admin_id)
    if admin_id == actor_id:
        raise AppError(
            status_code=status.HTTP_403_FORBIDDEN,
            code="use_change_password",
            message="Use change password to update your own password",
        )
    validate_password(new_password, admin.username)
    admin.password_hash = hash_password(new_password)
    admin.token_version += 1
    save_config(cfg)
    return admin


def change_admin_password(admin_id: int, current_password: str, new_password: str) -> None:
    cfg = load_config()
    admin = _find_admin(cfg, admin_id)
    if not verify_password(current_password, admin.password_hash):
        raise AppError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="current_password_incorrect",
            message="Current password is incorrect.",
        )
    validate_password(new_password, admin.username)
    admin.password_hash = hash_password(new_password)
    admin.token_version += 1
    save_config(cfg)
