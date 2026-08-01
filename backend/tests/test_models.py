import pytest
from datetime import datetime, date, timezone
from pydantic import ValidationError

from models import (
    CPORecord,
    Menu,
    Pizza,
    Order,
    SessionFile,
    SessionStatusResponse,
    CreateMenuRequest,
    CreatePizzaRequest,
    CreateSessionRequest,
    OrderItem,
    SubmitOrderRequest,
    TeamInvite,
    TeamRecord,
    UpdateCurrencyRequest,
    UpdateMemberIdentifierRequest,
)


def _now():
    return datetime.now(timezone.utc)


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


def test_menu_defaults():
    m = Menu(id="m1", team_id="t1", name="Pizzas")
    assert m.is_default is False
    assert m.pizzas == []
    assert m.pizzeria_url is None


def test_menu_url_validator_clears_bad_scheme():
    """Loading a menu with a bad stored url must not crash — url is cleared."""
    m = Menu(id="m1", team_id="t1", name="Pizzas", pizzeria_url="javascript:alert(1)")
    assert m.pizzeria_url is None


def test_create_menu_request_rejects_bad_url():
    with pytest.raises(ValidationError):
        CreateMenuRequest(name="Pizzas", pizzeria_url="ftp://bad.example.com")


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
    assert req.menu_id is None   # optional; server falls back to the default menu


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
        team_id="t1",
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
# CPORecord — login-only fields (team_name/currency/etc. live on TeamRecord)
# ---------------------------------------------------------------------------

def test_cpo_record_round_trip():
    rec = CPORecord(
        id="x",
        team_id="t1",
        username="alice",
        email="alice@example.com",
        password_hash="$2b$12$hash",
        created_at=_now(),
    )
    assert rec.team_id == "t1"
    assert rec.token_version == 0


# ---------------------------------------------------------------------------
# TeamRecord
# ---------------------------------------------------------------------------

def _team_record(**overrides) -> TeamRecord:
    fields = {
        "id": "t1",
        "team_name": "Eng",
        "unique_link": "abcdefghij123456",
        "created_at": _now(),
    }
    fields.update(overrides)
    return TeamRecord(**fields)


def test_team_record_currency_defaults_to_chf():
    """Existing config.json records without a currency field deserialize to CHF."""
    assert _team_record().currency == "CHF"


def test_team_record_currency_persists():
    assert _team_record(currency="€").currency == "€"


def test_team_record_stats_reset_at_defaults_none():
    assert _team_record().stats_reset_at is None


# ---------------------------------------------------------------------------
# TeamInvite
# ---------------------------------------------------------------------------

def test_team_invite_defaults():
    invite = TeamInvite(
        id="i1",
        team_id="t1",
        token="tok1234567890123",
        created_by_cpo_id="c1",
        created_at=_now(),
        expires_at=_now(),
    )
    assert invite.used_at is None


def test_team_invite_used_at_persists():
    invite = TeamInvite(
        id="i1",
        team_id="t1",
        token="tok1234567890123",
        created_by_cpo_id="c1",
        created_at=_now(),
        expires_at=_now(),
        used_at=_now(),
    )
    assert invite.used_at is not None


def test_session_status_response_currency_defaults_to_chf():
    r = SessionStatusResponse(session_id="s1", status="closed", team_name="Eng", pizzas=[])
    assert r.currency == "CHF"


def test_update_currency_request_rejects_empty():
    with pytest.raises(ValidationError):
        UpdateCurrencyRequest(currency="")


def test_update_currency_request_rejects_too_long():
    with pytest.raises(ValidationError):
        UpdateCurrencyRequest(currency="TOOLONGVALUE")


# ---------------------------------------------------------------------------
# Member identifier (lives on TeamRecord, not CPORecord)
# ---------------------------------------------------------------------------

def test_team_record_member_identifier_defaults_to_name():
    assert _team_record().member_identifier == "name"


def test_team_record_member_identifier_accepts_email():
    assert _team_record(member_identifier="email").member_identifier == "email"


def test_team_record_coerces_unknown_member_identifier_to_name():
    """load_config() validates every team in one pass — a junk value must not
    raise, or one bad row breaks requests for every team."""
    assert _team_record(member_identifier="phone").member_identifier == "name"


def test_team_record_coerces_null_member_identifier_to_name():
    assert _team_record(member_identifier=None).member_identifier == "name"


def test_session_status_response_member_identifier_defaults_to_name():
    r = SessionStatusResponse(session_id="s1", status="closed", team_name="Eng", pizzas=[])
    assert r.member_identifier == "name"


def test_update_member_identifier_request_accepts_both_modes():
    assert UpdateMemberIdentifierRequest(member_identifier="name").member_identifier == "name"
    assert UpdateMemberIdentifierRequest(member_identifier="email").member_identifier == "email"


def test_update_member_identifier_request_rejects_unknown_value():
    with pytest.raises(ValidationError):
        UpdateMemberIdentifierRequest(member_identifier="phone")


def test_order_item_accepts_254_char_value():
    """RFC 5321 caps an address at 254 chars; the model must not cut below it."""
    item = OrderItem(member_name="a" * 245 + "@test.com", pizza_id="p1")
    assert len(item.member_name) == 254


def test_order_item_rejects_255_char_value():
    with pytest.raises(ValidationError):
        OrderItem(member_name="a" * 255, pizza_id="p1")
