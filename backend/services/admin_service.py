from datetime import timezone, datetime

from fastapi import HTTPException, status

from models import AdminRecord, CPORecord
from password_policy import validate_password
from storage import delete_admin as storage_delete_admin
from storage import insert_admin, load_config, save_config
from utils import generate_link, hash_password, new_id, verify_password

_NOT_FOUND = "CPO not found"
_ADMIN_NOT_FOUND = "Admin not found"
_USERNAME_EXISTS = "Username already exists"


def _username_taken(cfg, username: str) -> bool:
    """Case-insensitive check across both roles — login resolves admins first,
    so a cross-role duplicate would shadow the CPO account."""
    lowered = username.lower()
    return any(a.username.lower() == lowered for a in cfg.admins) or any(
        c.username.lower() == lowered for c in cfg.cpos
    )


def list_cpos() -> list[CPORecord]:
    return load_config().cpos


def create_cpo(username: str, email: str, team_name: str, initial_password: str) -> CPORecord:
    cfg = load_config()

    if _username_taken(cfg, username):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_USERNAME_EXISTS)
    if any(c.email.lower() == email.lower() for c in cfg.cpos):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists")

    validate_password(initial_password, username)

    existing_links = {c.unique_link for c in cfg.cpos}
    link = generate_link()
    while link in existing_links:
        link = generate_link()

    cpo = CPORecord(
        id=new_id(),
        username=username,
        email=email,
        password_hash=hash_password(initial_password),
        team_name=team_name,
        unique_link=link,
        created_at=datetime.now(tz=timezone.utc),
    )
    cfg.cpos.append(cpo)
    save_config(cfg)
    return cpo


def update_cpo(cpo_id: str, email: str, team_name: str) -> CPORecord:
    cfg = load_config()
    cpo = next((c for c in cfg.cpos if c.id == cpo_id), None)
    if cpo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND)
    if any(c.email.lower() == email.lower() and c.id != cpo_id for c in cfg.cpos):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists")
    cpo.email = email
    cpo.team_name = team_name
    save_config(cfg)
    return cpo


def delete_cpo(cpo_id: str) -> None:
    cfg = load_config()
    before = len(cfg.cpos)
    cfg.cpos = [c for c in cfg.cpos if c.id != cpo_id]
    if len(cfg.cpos) == before:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND)
    save_config(cfg)


def reset_password(cpo_id: str, new_password: str) -> CPORecord:
    cfg = load_config()
    cpo = next((c for c in cfg.cpos if c.id == cpo_id), None)
    if cpo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND)
    validate_password(new_password, cpo.username)
    cpo.password_hash = hash_password(new_password)
    cpo.token_version += 1
    save_config(cfg)
    return cpo


# ---------------------------------------------------------------------------
# Admin account management
# ---------------------------------------------------------------------------

def _find_admin(cfg, admin_id: int) -> AdminRecord:
    admin = next((a for a in cfg.admins if a.id == admin_id), None)
    if admin is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_ADMIN_NOT_FOUND)
    return admin


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
    if _username_taken(cfg, username):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_USERNAME_EXISTS)
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
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot delete your own account",
        )
    if len(cfg.admins) <= 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete the last admin account",
        )
    storage_delete_admin(admin_id)


def reset_admin_password(actor_id: int, admin_id: int, new_password: str) -> AdminRecord:
    cfg = load_config()
    admin = _find_admin(cfg, admin_id)
    if admin_id == actor_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Use change password to update your own password",
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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect.",
        )
    validate_password(new_password, admin.username)
    admin.password_hash = hash_password(new_password)
    admin.token_version += 1
    save_config(cfg)
