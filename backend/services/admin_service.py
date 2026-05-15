from datetime import timezone, datetime

from fastapi import HTTPException, status

from models import CPORecord
from storage import load_config, save_config
from utils import generate_link, hash_password, new_id

_NOT_FOUND = "CPO not found"


def list_cpos() -> list[CPORecord]:
    return load_config().cpos


def create_cpo(username: str, email: str, team_name: str, initial_password: str) -> CPORecord:
    cfg = load_config()

    if any(c.username.lower() == username.lower() for c in cfg.cpos):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")
    if any(c.email.lower() == email.lower() for c in cfg.cpos):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists")

    cpo = CPORecord(
        id=new_id(),
        username=username,
        email=email,
        password_hash=hash_password(initial_password),
        team_name=team_name,
        unique_link=generate_link(),
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
    cpo.password_hash = hash_password(new_password)
    save_config(cfg)
    return cpo
