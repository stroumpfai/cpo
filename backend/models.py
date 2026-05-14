"""
Pydantic models for all stored entities and API contracts.

Storage models (suffix *Record / *File) map directly to JSON on disk.
API models (request/response) are separate to decouple storage from the wire format.
"""
from __future__ import annotations

from datetime import date, datetime, time
from typing import Literal
from pydantic import BaseModel, EmailStr, Field, field_validator


# ---------------------------------------------------------------------------
# Storage models — config.json
# ---------------------------------------------------------------------------

class AdminRecord(BaseModel):
    username: str
    password_hash: str
    created_at: datetime


class CPORecord(BaseModel):
    id: str
    username: str
    email: str
    password_hash: str
    team_name: str
    unique_link: str          # per-team permanent link (16+ alphanumeric chars)
    created_at: datetime


class ConfigFile(BaseModel):
    admin: AdminRecord
    cpos: list[CPORecord] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Storage models — {cpo_id}/menu.json
# ---------------------------------------------------------------------------

class Pizza(BaseModel):
    id: str
    name: str
    price: float = Field(ge=0.01)


class MenuFile(BaseModel):
    cpo_id: str
    pizzas: list[Pizza] = Field(default_factory=list)


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


class SessionFile(BaseModel):
    id: str
    cpo_id: str
    team_name: str
    session_date: date
    start_time: str           # "HH:MM"
    end_time: str             # "HH:MM"
    grace_period_minutes: int = 2
    created_at: datetime
    orders: list[Order] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# API — auth
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    role: Literal["admin", "cpo"]
    expires_in: int = 2592000   # 30 days in seconds


# ---------------------------------------------------------------------------
# API — admin
# ---------------------------------------------------------------------------

class CreateCPORequest(BaseModel):
    username: str
    email: EmailStr
    team_name: str
    initial_password: str = Field(min_length=8)


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=8)


class CPOResponse(BaseModel):
    id: str
    username: str
    email: str
    team_name: str
    unique_link: str
    created_at: datetime


# ---------------------------------------------------------------------------
# API — CPO / sessions
# ---------------------------------------------------------------------------

class CreateSessionRequest(BaseModel):
    session_date: date
    start_time: str   # "HH:MM"
    end_time: str     # "HH:MM"
    grace_period_minutes: int = Field(default=2, ge=0)

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


# ---------------------------------------------------------------------------
# API — CPO / menu
# ---------------------------------------------------------------------------

class CreatePizzaRequest(BaseModel):
    name: str = Field(min_length=1)
    price: float = Field(ge=0.01)


class UpdatePizzaRequest(BaseModel):
    name: str = Field(min_length=1)
    price: float = Field(ge=0.01)


class PizzaResponse(BaseModel):
    id: str
    name: str
    price: float


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


class PizzeriaRow(BaseModel):
    pizza_name: str
    count: int
    total_price: float


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


class SubmitOrderRequest(BaseModel):
    member_name: str = Field(min_length=1)
    pizza_ids: list[str] = Field(min_length=1)


class SubmitOrderResponse(BaseModel):
    status: str = "submitted"
    member_name: str
    orders_created: int
    order_ids: list[str]
