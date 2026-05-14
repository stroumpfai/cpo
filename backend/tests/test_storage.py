import json
import os
import pytest
from datetime import date, datetime
from pathlib import Path

import models
import storage
import utils
from models import (
    AdminRecord,
    ConfigFile,
    CPORecord,
    MenuFile,
    Order,
    Pizza,
    SessionFile,
)


def _now():
    return datetime.utcnow()


@pytest.fixture(autouse=True)
def isolated_paths(tmp_path, monkeypatch):
    """Redirect CONFIG_PATH and DATA_DIR to a temp directory for each test."""
    config_file = tmp_path / "config" / "config.json"
    data_dir = tmp_path / "data"
    monkeypatch.setattr(storage, "CONFIG_PATH", str(config_file))
    monkeypatch.setattr(storage, "DATA_DIR", str(data_dir))
    # also patch config module constants used in storage helpers
    import config as cfg_module
    monkeypatch.setattr(cfg_module, "CONFIG_PATH", str(config_file))
    monkeypatch.setattr(cfg_module, "DATA_DIR", str(data_dir))
    return tmp_path


def _make_config(tmp_path) -> ConfigFile:
    admin = AdminRecord(
        username="admin",
        password_hash=utils.hash_password("secret"),
        created_at=_now(),
    )
    cpo = CPORecord(
        id=utils.new_id(),
        username="john",
        email="john@example.com",
        password_hash=utils.hash_password("pass1234"),
        team_name="Engineering",
        unique_link=utils.generate_link(),
        created_at=_now(),
    )
    return ConfigFile(admin=admin, cpos=[cpo])


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def test_save_and_load_config(tmp_path):
    cfg = _make_config(tmp_path)
    storage.save_config(cfg)
    loaded = storage.load_config()
    assert loaded.admin.username == "admin"
    assert len(loaded.cpos) == 1
    assert loaded.cpos[0].username == "john"


def test_config_missing_raises():
    with pytest.raises(FileNotFoundError):
        storage.load_config()


def test_atomic_write_does_not_leave_tmp_on_success(tmp_path):
    cfg = _make_config(tmp_path)
    storage.save_config(cfg)
    config_dir = Path(str(tmp_path / "config"))
    tmp_files = list(config_dir.glob("*.tmp"))
    assert tmp_files == []


# ---------------------------------------------------------------------------
# Menu
# ---------------------------------------------------------------------------

def test_menu_missing_returns_empty(tmp_path):
    menu = storage.load_menu("cpo-1")
    assert menu.pizzas == []


def test_save_and_load_menu(tmp_path):
    menu = MenuFile(
        cpo_id="cpo-1",
        pizzas=[Pizza(id="p1", name="Margherita", price=12.50)],
    )
    storage.save_menu(menu)
    loaded = storage.load_menu("cpo-1")
    assert len(loaded.pizzas) == 1
    assert loaded.pizzas[0].name == "Margherita"


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

def _make_session(cpo_id="cpo-1") -> SessionFile:
    return SessionFile(
        id=utils.new_id(),
        cpo_id=cpo_id,
        team_name="Engineering",
        session_date=date(2026, 5, 14),
        start_time="11:30",
        end_time="12:00",
        created_at=_now(),
    )


def test_save_and_load_session(tmp_path):
    s = _make_session()
    storage.save_session(s)
    loaded = storage.load_session(s.cpo_id, s.id)
    assert loaded is not None
    assert loaded.id == s.id
    assert loaded.orders == []


def test_load_session_missing_returns_none():
    assert storage.load_session("cpo-1", "nonexistent") is None


def test_list_sessions_empty():
    assert storage.list_sessions("cpo-1") == []


def test_list_sessions_excludes_menu(tmp_path):
    s = _make_session()
    storage.save_session(s)
    storage.save_menu(MenuFile(cpo_id=s.cpo_id, pizzas=[]))
    sessions = storage.list_sessions(s.cpo_id)
    assert len(sessions) == 1


# ---------------------------------------------------------------------------
# Orders inside sessions
# ---------------------------------------------------------------------------

def _make_order(session_id: str) -> Order:
    return Order(
        id=utils.new_id(),
        session_id=session_id,
        member_name="Alice",
        pizza_id="p1",
        pizza_name="Margherita",
        pizza_price=12.50,
        total_price=12.50,
        created_at=_now(),
        client_ip="127.0.0.1",
    )


def test_add_order(tmp_path):
    s = _make_session()
    storage.save_session(s)
    order = _make_order(s.id)
    storage.add_order_to_session(s.cpo_id, s.id, order)
    loaded = storage.load_session(s.cpo_id, s.id)
    assert len(loaded.orders) == 1
    assert loaded.orders[0].member_name == "Alice"


def test_delete_order(tmp_path):
    s = _make_session()
    storage.save_session(s)
    o = _make_order(s.id)
    storage.add_order_to_session(s.cpo_id, s.id, o)
    result = storage.delete_order_from_session(s.cpo_id, s.id, o.id)
    assert result is True
    loaded = storage.load_session(s.cpo_id, s.id)
    assert loaded.orders == []


def test_delete_nonexistent_order(tmp_path):
    s = _make_session()
    storage.save_session(s)
    result = storage.delete_order_from_session(s.cpo_id, s.id, "bad-id")
    assert result is False


# ---------------------------------------------------------------------------
# utils — session status
# ---------------------------------------------------------------------------

from utils import compute_session_status
from unittest.mock import patch


def test_status_upcoming():
    with patch("utils.now_utc", return_value=datetime(2026, 5, 14, 10, 0)):
        assert compute_session_status(date(2026, 5, 14), "11:30", "12:00") == "upcoming"


def test_status_active():
    with patch("utils.now_utc", return_value=datetime(2026, 5, 14, 11, 45)):
        assert compute_session_status(date(2026, 5, 14), "11:30", "12:00") == "active"


def test_status_in_grace_period():
    with patch("utils.now_utc", return_value=datetime(2026, 5, 14, 12, 1)):
        assert compute_session_status(date(2026, 5, 14), "11:30", "12:00") == "active"


def test_status_closed():
    with patch("utils.now_utc", return_value=datetime(2026, 5, 14, 12, 3)):
        assert compute_session_status(date(2026, 5, 14), "11:30", "12:00") == "closed"


# ---------------------------------------------------------------------------
# utils — passwords and link generation
# ---------------------------------------------------------------------------

def test_password_hash_and_verify():
    h = utils.hash_password("mysecret")
    assert utils.verify_password("mysecret", h)
    assert not utils.verify_password("wrong", h)


def test_generate_link_length():
    link = utils.generate_link()
    assert len(link) >= 16
    assert link.isalnum()
