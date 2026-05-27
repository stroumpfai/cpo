"""
JSON file I/O layer.  All writes are atomic (write to tmp, then rename).

Layout:
  CONFIG_PATH              → ConfigFile   (admin + CPO accounts)
  DATA_DIR/{cpo_id}/menu.json  → MenuFile
  DATA_DIR/{cpo_id}/{session_id}.json → SessionFile (includes orders list)
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Optional

from config import CONFIG_PATH, DATA_DIR
from models import ConfigFile, MenuFile, Order, SessionFile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(path: str | Path, data: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        os.replace(tmp, path)
    except Exception:
        os.unlink(tmp)
        raise


def _cpo_dir(cpo_id: str) -> Path:
    return Path(DATA_DIR) / cpo_id


def _session_path(cpo_id: str, session_id: str) -> Path:
    return _cpo_dir(cpo_id) / f"{session_id}.json"


def _menu_path(cpo_id: str) -> Path:
    return _cpo_dir(cpo_id) / "menu.json"


# ---------------------------------------------------------------------------
# Config (admin + CPO accounts)
# ---------------------------------------------------------------------------

def load_config() -> ConfigFile:
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(
            f"Config file not found at {CONFIG_PATH}. "
            "Mount a config volume or set CONFIG_PATH."
        )
    return ConfigFile.model_validate(_load(CONFIG_PATH))


def save_config(cfg: ConfigFile) -> None:
    _save(CONFIG_PATH, cfg.model_dump(mode="json"))


# ---------------------------------------------------------------------------
# Menu
# ---------------------------------------------------------------------------

def load_menu(cpo_id: str) -> MenuFile:
    path = _menu_path(cpo_id)
    if not path.exists():
        return MenuFile(cpo_id=cpo_id)
    return MenuFile.model_validate(_load(path))


def save_menu(menu: MenuFile) -> None:
    _save(_menu_path(menu.cpo_id), menu.model_dump(mode="json"))


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

def load_session(cpo_id: str, session_id: str) -> Optional[SessionFile]:
    path = _session_path(cpo_id, session_id)
    if not path.exists():
        return None
    return SessionFile.model_validate(_load(path))


def save_session(session: SessionFile) -> None:
    _save(_session_path(session.cpo_id, session.id), session.model_dump(mode="json"))


def list_sessions(cpo_id: str) -> list[SessionFile]:
    cpo_dir = _cpo_dir(cpo_id)
    if not cpo_dir.exists():
        return []
    sessions = []
    for p in cpo_dir.glob("*.json"):
        if p.name == "menu.json":
            continue
        sessions.append(SessionFile.model_validate(_load(p)))
    sessions.sort(key=lambda s: s.created_at)
    return sessions


def find_cpo_by_link(unique_link: str) -> Optional["CPORecord"]:
    """Return the CPO whose permanent team link matches unique_link."""
    from models import CPORecord  # avoid circular at module level
    if not os.path.exists(CONFIG_PATH):
        return None
    cfg = load_config()
    return next((c for c in cfg.cpos if c.unique_link == unique_link), None)


def find_session_by_link(unique_link: str) -> Optional[tuple[str, SessionFile]]:
    """Return (cpo_id, session) for the session whose CPO owns unique_link."""
    # unique_link lives on the CPO record; look it up via config
    from config import CONFIG_PATH
    if not os.path.exists(CONFIG_PATH):
        return None
    cfg = load_config()
    cpo = next((c for c in cfg.cpos if c.unique_link == unique_link), None)
    if cpo is None:
        return None
    # find the most-recent active or upcoming session for this CPO
    sessions = list_sessions(cpo.id)
    # prefer active, then upcoming, then most recent
    for s in reversed(sessions):
        return cpo.id, s   # caller checks status
    return None


def add_order_to_session(cpo_id: str, session_id: str, order: Order) -> None:
    session = load_session(cpo_id, session_id)
    if session is None:
        raise ValueError(f"Session {session_id} not found")
    session.orders.append(order)
    save_session(session)


def delete_order_from_session(cpo_id: str, session_id: str, order_id: str) -> bool:
    session = load_session(cpo_id, session_id)
    if session is None:
        return False
    before = len(session.orders)
    session.orders = [o for o in session.orders if o.id != order_id]
    if len(session.orders) == before:
        return False
    save_session(session)
    return True


def set_order_received(cpo_id: str, session_id: str, order_id: str, received: bool) -> bool:
    session = load_session(cpo_id, session_id)
    if session is None:
        return False
    for order in session.orders:
        if order.id == order_id:
            order.received = received
            save_session(session)
            return True
    return False
