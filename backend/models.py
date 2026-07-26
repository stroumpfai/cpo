"""
Pydantic models for all stored entities and API contracts.

Storage models (suffix *Record / *File) map directly to JSON on disk.
API models (request/response) are separate to decouple storage from the wire format.
"""
from __future__ import annotations

from datetime import date, datetime, time
from typing import Annotated, Literal
from pydantic import BaseModel, EmailStr, Field, field_validator

_ALLOWED_URL_SCHEMES = ("http://", "https://")


# ---------------------------------------------------------------------------
# Storage models — config.json
# ---------------------------------------------------------------------------

class AdminRecord(BaseModel):
    id: int
    username: str
    password_hash: str
    created_at: datetime
    token_version: int = 0    # incremented on password reset to invalidate existing JWTs


class CPORecord(BaseModel):
    id: str
    username: str
    email: str
    password_hash: str
    team_name: str
    unique_link: str          # per-team permanent link (16+ alphanumeric chars)
    created_at: datetime
    token_version: int = 0    # incremented on password reset to invalidate existing JWTs
    currency: str = "CHF"     # prefix symbol/code shown on prices (e.g. CHF, €, $)


class ConfigFile(BaseModel):
    admins: list[AdminRecord]
    cpos: list[CPORecord] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Storage models — {cpo_id}/menu.json
# ---------------------------------------------------------------------------

class Pizza(BaseModel):
    id: str
    name: str
    price: float = Field(ge=0.01)


class MenuFile(BaseModel):
    """Legacy {cpo_id}/menu.json shape — used only by json_migration.py."""
    cpo_id: str
    pizzas: list[Pizza] = Field(default_factory=list)
    pizzeria_url: str | None = None

    @field_validator("pizzeria_url")
    @classmethod
    def validate_url(cls, v: str | None) -> str | None:
        if v is not None and not v.lower().startswith(_ALLOWED_URL_SCHEMES):
            return None   # silently clear rather than crash on load
        return v


class Menu(BaseModel):
    """A named menu row plus its items. A CPO can own several; one is default."""
    id: str
    cpo_id: str
    name: str
    is_default: bool = False
    pizzeria_url: str | None = None
    pizzas: list[Pizza] = Field(default_factory=list)

    @field_validator("pizzeria_url")
    @classmethod
    def validate_url(cls, v: str | None) -> str | None:
        if v is not None and not v.lower().startswith(_ALLOWED_URL_SCHEMES):
            return None   # silently clear rather than crash on load
        return v


# ---------------------------------------------------------------------------
# Storage models — {cpo_id}/{session_id}.json
# ---------------------------------------------------------------------------

class Order(BaseModel):
    id: str
    session_id: str
    member_name: str
    pizza_id: str
    pizza_name: str
    pizza_price: float
    quantity: int = 1
    total_price: float
    created_at: datetime
    client_ip: str
    comment: str | None = None
    received: bool = False


class SessionFile(BaseModel):
    id: str
    cpo_id: str
    team_name: str
    session_date: date
    start_time: str           # "HH:MM"
    end_time: str             # "HH:MM"
    grace_period_minutes: int = 2
    created_at: datetime
    closed_at: datetime | None = None   # set by force-close; overrides time-based status
    menu_id: str | None = None          # None on legacy sessions or after menu deletion
    orders: list[Order] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# API — auth
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str = Field(max_length=64)
    password: str = Field(max_length=1024)


class LoginResponse(BaseModel):
    token: str
    role: Literal["admin", "cpo"]
    expires_in: int = 1209600   # 14 days in seconds


# ---------------------------------------------------------------------------
# API — admin
# ---------------------------------------------------------------------------

class CreateCPORequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    email: EmailStr
    team_name: str = Field(min_length=1, max_length=128)
    initial_password: str = Field(min_length=8, max_length=1024)


class CreateAdminRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    initial_password: str = Field(min_length=8, max_length=1024)


class AdminResponse(BaseModel):
    id: int
    username: str
    created_at: datetime
    is_self: bool = False


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=8, max_length=1024)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(max_length=1024)
    new_password: str = Field(min_length=8, max_length=1024)


class UpdateCPORequest(BaseModel):
    email: EmailStr
    team_name: str = Field(min_length=1, max_length=128)


class CPOResponse(BaseModel):
    id: str
    username: str
    email: str
    team_name: str
    unique_link: str
    created_at: datetime
    currency: str


class SessionUsageRow(BaseModel):
    """Internal storage->service row: one session plus its order count."""
    id: str
    cpo_id: str
    session_date: date
    start_time: str
    end_time: str
    grace_period_minutes: int
    created_at: datetime
    closed_at: datetime | None = None
    order_count: int


class SessionUsageItem(BaseModel):
    session_id: str
    session_date: date
    start_time: str   # "HH:MM" UTC
    end_time: str     # "HH:MM" UTC
    order_count: int


class CPOUsageStats(BaseModel):
    cpo_id: str
    team_name: str
    past_session_count: int
    total_orders: int
    latest_sessions: list[SessionUsageItem]   # up to 3, newest first


# ---------------------------------------------------------------------------
# API — CPO / sessions
# ---------------------------------------------------------------------------

class CreateSessionRequest(BaseModel):
    session_date: date
    start_time: str   # "HH:MM"
    end_time: str     # "HH:MM"
    grace_period_minutes: int = Field(default=2, ge=0)
    menu_id: str | None = None   # omitted → the CPO's default menu

    @field_validator("start_time", "end_time")
    @classmethod
    def validate_time_format(cls, v: str) -> str:
        time.fromisoformat(v)   # raises ValueError if invalid
        return v


class SessionResponse(BaseModel):
    id: str
    cpo_id: str
    team_name: str
    unique_link: str
    session_date: date
    start_time: str
    end_time: str
    grace_period_minutes: int
    status: Literal["upcoming", "active", "closed"]
    created_at: datetime
    menu_id: str | None = None


# ---------------------------------------------------------------------------
# API — CPO / menu
# ---------------------------------------------------------------------------

class CreatePizzaRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    price: float = Field(ge=0.01)


class UpdatePizzaRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    price: float = Field(ge=0.01)


class PizzaResponse(BaseModel):
    id: str
    name: str
    price: float


class MenuResponse(BaseModel):
    id: str
    name: str
    is_default: bool
    pizzeria_url: str | None = None
    pizza_count: int


class CreateMenuRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    pizzeria_url: str | None = None

    @field_validator("pizzeria_url")
    @classmethod
    def validate_url(cls, v: str | None) -> str | None:
        if v is not None and not v.lower().startswith(_ALLOWED_URL_SCHEMES):
            raise ValueError("pizzeria_url must start with http:// or https://")
        return v


class UpdateMenuRequest(BaseModel):
    """PATCH semantics: omitted fields are untouched, explicit null clears the url."""
    name: str | None = Field(default=None, min_length=1, max_length=100)
    pizzeria_url: str | None = None

    @field_validator("pizzeria_url")
    @classmethod
    def validate_url(cls, v: str | None) -> str | None:
        if v is not None and not v.lower().startswith(_ALLOWED_URL_SCHEMES):
            raise ValueError("pizzeria_url must start with http:// or https://")
        return v


# ---------------------------------------------------------------------------
# API — CPO / menu export-import
# ---------------------------------------------------------------------------

class PortablePizzaItem(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    price: float = Field(ge=0.01)


class MenuPortable(BaseModel):
    dishes: list[PortablePizzaItem] = Field(max_length=500)
    url: str | None = None

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str | None) -> str | None:
        if v is not None and not v.lower().startswith(_ALLOWED_URL_SCHEMES):
            raise ValueError("url must start with http:// or https://")
        return v


# ---------------------------------------------------------------------------
# API — CPO / summary
# ---------------------------------------------------------------------------

class DistributionRow(BaseModel):
    order_id: str
    member_name: str
    client_ip: str
    pizza_name: str
    price: float
    created_at: datetime
    comment: str | None = None
    received: bool = False


class CommentCount(BaseModel):
    text: str
    count: int


class PizzeriaRow(BaseModel):
    pizza_name: str
    count: int
    total_price: float
    comments: list[CommentCount] = []


class SetReceivedRequest(BaseModel):
    received: bool


class SummaryResponse(BaseModel):
    session_id: str
    status: Literal["upcoming", "active", "closed"]
    distribution: list[DistributionRow]
    pizzeria: list[PizzeriaRow]
    total_orders: int
    total_price: float


# ---------------------------------------------------------------------------
# API — team orders (no auth)
# ---------------------------------------------------------------------------

class SessionStatusResponse(BaseModel):
    session_id: str
    status: Literal["upcoming", "active", "closed"]
    team_name: str
    pizzas: list[PizzaResponse]
    message: str | None = None
    # Timing fields included so the client can render a countdown
    session_date: str | None = None   # "YYYY-MM-DD"
    end_time: str | None = None       # "HH:MM"
    pizzeria_url: str | None = None
    currency: str = "CHF"


class UpdateCurrencyRequest(BaseModel):
    currency: str = Field(min_length=1, max_length=10)


class UpdateTeamNameRequest(BaseModel):
    team_name: str = Field(min_length=1, max_length=128)


class OrderItem(BaseModel):
    member_name: str = Field(min_length=1, max_length=100)
    pizza_id: str
    comment: Annotated[str, Field(min_length=1, max_length=100)] | None = None


class SubmitOrderRequest(BaseModel):
    items: list[OrderItem] = Field(min_length=1, max_length=50)


class SubmitOrderResponse(BaseModel):
    status: str = "submitted"
    orders_created: int
    order_ids: list[str]
