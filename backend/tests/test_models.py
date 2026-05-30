import pytest
from datetime import datetime, date
from pydantic import ValidationError

from models import (
    CPORecord,
    Pizza,
    Order,
    SessionFile,
    SessionStatusResponse,
    CreatePizzaRequest,
    CreateSessionRequest,
    SubmitOrderRequest,
    UpdateCurrencyRequest,
)


def _now():
    return datetime.utcnow()


# ---------------------------------------------------------------------------
# Pizza / menu
# ---------------------------------------------------------------------------

def test_pizza_valid():
    p = Pizza(id="1", name="Margherita", price=12.50)
    assert p.price == 12.50


def test_pizza_price_too_low():
    with pytest.raises(ValidationError):
        Pizza(id="1", name="Margherita", price=0.0)


def test_pizza_price_minimum():
    p = Pizza(id="1", name="Margherita", price=0.01)
    assert p.price == 0.01


def test_create_pizza_request_invalid_name():
    with pytest.raises(ValidationError):
        CreatePizzaRequest(name="", price=10.0)


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------

def test_create_session_valid_times():
    req = CreateSessionRequest(
        session_date=date(2026, 5, 14),
        start_time="11:30",
        end_time="12:00",
    )
    assert req.grace_period_minutes == 2


def test_create_session_invalid_time_format():
    with pytest.raises(ValidationError):
        CreateSessionRequest(
            session_date=date(2026, 5, 14),
            start_time="25:00",
            end_time="12:00",
        )


def test_session_file_defaults():
    s = SessionFile(
        id="s1",
        cpo_id="c1",
        team_name="Eng",
        session_date=date(2026, 5, 14),
        start_time="11:30",
        end_time="12:00",
        created_at=_now(),
    )
    assert s.orders == []
    assert s.grace_period_minutes == 2


# ---------------------------------------------------------------------------
# Order
# ---------------------------------------------------------------------------

def test_order_round_trip():
    o = Order(
        id="o1",
        session_id="s1",
        member_name="Alice",
        pizza_id="p1",
        pizza_name="Margherita",
        pizza_price=12.50,
        total_price=12.50,
        created_at=_now(),
        client_ip="127.0.0.1",
    )
    assert o.quantity == 1
    assert o.total_price == 12.50


# ---------------------------------------------------------------------------
# SubmitOrderRequest validation
# ---------------------------------------------------------------------------

def test_submit_order_empty_name():
    with pytest.raises(ValidationError):
        SubmitOrderRequest(member_name="", pizza_ids=["p1"])


def test_submit_order_empty_pizza_list():
    with pytest.raises(ValidationError):
        SubmitOrderRequest(member_name="Alice", pizza_ids=[])


# ---------------------------------------------------------------------------
# Currency
# ---------------------------------------------------------------------------

def test_cpo_record_currency_defaults_to_chf():
    """Existing config.json records without a currency field deserialize to CHF."""
    rec = CPORecord(
        id="x",
        username="alice",
        email="alice@example.com",
        password_hash="$2b$12$hash",
        team_name="Eng",
        unique_link="abcdefghij123456",
        created_at=_now(),
    )
    assert rec.currency == "CHF"


def test_cpo_record_currency_persists():
    rec = CPORecord(
        id="x",
        username="alice",
        email="alice@example.com",
        password_hash="$2b$12$hash",
        team_name="Eng",
        unique_link="abcdefghij123456",
        created_at=_now(),
        currency="€",
    )
    assert rec.currency == "€"


def test_session_status_response_currency_defaults_to_chf():
    r = SessionStatusResponse(session_id="s1", status="closed", team_name="Eng", pizzas=[])
    assert r.currency == "CHF"


def test_update_currency_request_rejects_empty():
    with pytest.raises(ValidationError):
        UpdateCurrencyRequest(currency="")


def test_update_currency_request_rejects_too_long():
    with pytest.raises(ValidationError):
        UpdateCurrencyRequest(currency="TOOLONGVALUE")
