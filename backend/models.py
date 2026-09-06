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

# UI language tags. Adding a fifth language means adding its tag here (and a
# locale file on the front end) — nothing else in this module changes.
Language = Literal["en", "de-CH", "fr-CH", "it-CH"]
_LANGUAGE_TAGS = ("en", "de-CH", "fr-CH", "it-CH")


class LanguagePreference(BaseModel):
    """Mixin for login records: the account's own UI language.

    Unlike member_identifier (a team setting), this belongs to the login row —
    two CPOs sharing a team can read the app in different languages.
    None = no explicit choice, follow the browser.
    """
    language: Language | None = None

    @field_validator("language", mode="before")
    @classmethod
    def coerce_language(cls, v):
        # load_config() validates every admin/CPO row in one pass, so a tag
        # this build no longer supports would break requests for every
        # account, not just its owner. Fall back to "follow the browser"
        # silently, as TeamRecord.coerce_member_identifier does.
        return v if v in _LANGUAGE_TAGS else None


# ---------------------------------------------------------------------------
# Storage models — config.json
# ---------------------------------------------------------------------------

class AdminRecord(LanguagePreference):
    id: int
    username: str
    password_hash: str
    created_at: datetime
    token_version: int = 0    # incremented on password reset to invalidate existing JWTs


class TeamRecord(BaseModel):
    """A team: the thing that owns menus/sessions/orders and has a public
    ordering link. One or more CPORecords (logins) can belong to one team."""
    id: str
    team_name: str
    unique_link: str          # permanent link (16+ alphanumeric chars)
    created_at: datetime
    currency: str = "CHF"     # prefix symbol/code shown on prices (e.g. CHF, €, $)
    # What the public ordering form asks team members for. CPOs who announce a
    # delivery by email need addresses; the ones who shout across the office don't.
    member_identifier: Literal["name", "email"] = "name"
    # Set by the stats page's "reset counters" action; None = count all history.
    stats_reset_at: datetime | None = None
    # Preselects the grace period stepper on the "new session" form.
    default_grace_period_minutes: int = 2

    @field_validator("member_identifier", mode="before")
    @classmethod
    def coerce_member_identifier(cls, v):
        # load_config() validates every team row in one pass, so an unexpected
        # or NULL value here would break requests for every team, not just
        # this one. Repair silently instead, as MenuFile.validate_url does.
        return v if v in ("name", "email") else "name"


class CPORecord(LanguagePreference):
    """A CPO login. Several can share one team_id — see TeamRecord."""
    id: str
    team_id: str
    username: str
    email: str
    password_hash: str
    created_at: datetime
    token_version: int = 0    # incremented on password reset to invalidate existing JWTs


class TeamInvite(BaseModel):
    id: str
    team_id: str
    token: str
    created_by_cpo_id: str
    created_at: datetime
    expires_at: datetime
    used_at: datetime | None = None


class ConfigFile(BaseModel):
    admins: list[AdminRecord]
    cpos: list[CPORecord] = Field(default_factory=list)
    teams: list[TeamRecord] = Field(default_factory=list)


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
    """A named menu row plus its items. A team can own several; one is default."""
    id: str
    team_id: str
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
    team_id: str
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
# API — meta
# ---------------------------------------------------------------------------

class VersionResponse(BaseModel):
    """Build metadata, baked in at image build time (see the Dockerfile)."""
    version: str
    commit: str


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


class AdminProfileResponse(BaseModel):
    """An admin's own view of themselves — used by GET /admin/me."""
    id: int
    username: str
    language: Language | None = None


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=8, max_length=1024)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(max_length=1024)
    new_password: str = Field(min_length=8, max_length=1024)


class UpdateCPOEmailRequest(BaseModel):
    """Admin editing a single login's email (team_name is team-scoped now —
    see UpdateTeamNameRequest / PUT /admin/teams/{team_id})."""
    email: EmailStr


class CPOResponse(BaseModel):
    """A CPO's own view of themselves plus their team — used by GET /cpo/me."""
    id: str
    username: str
    email: str
    team_id: str
    team_name: str
    unique_link: str
    created_at: datetime
    currency: str
    member_identifier: Literal["name", "email"]
    default_grace_period_minutes: int
    language: Language | None = None   # this login's own UI language; None = follow the browser


class TeamMemberResponse(BaseModel):
    """One CPO login, as listed among a team's members (self-service or admin)."""
    id: str
    username: str
    email: str
    created_at: datetime
    is_self: bool = False


class AdminTeamResponse(BaseModel):
    """A team plus its member logins, as shown on the admin CPO management screen."""
    team_id: str
    team_name: str
    unique_link: str
    currency: str
    member_identifier: Literal["name", "email"]
    created_at: datetime
    members: list[TeamMemberResponse]


class SessionUsageRow(BaseModel):
    """Internal storage->service row: one session plus its order count."""
    id: str
    team_id: str
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
    team_id: str
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
    team_id: str
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
# API — CPO / statistics
# ---------------------------------------------------------------------------

class StatsSessionUsageRow(BaseModel):
    """Internal storage->service row: one session plus its summed item count."""
    id: str
    session_date: date
    start_time: str
    end_time: str
    grace_period_minutes: int
    closed_at: datetime | None = None
    item_count: int


class StatsSessionRow(BaseModel):
    session_id: str
    session_date: date
    start_time: str
    end_time: str
    status: Literal["upcoming", "active", "closed"]
    item_count: int   # sum(orders.quantity) for that session


class StatsPlateRow(BaseModel):
    pizza_name: str
    count: int


class StatsPersonRow(BaseModel):
    member_name: str
    count: int


class MenuStats(BaseModel):
    menu_id: str
    menu_name: str
    use_count: int   # sessions that served this menu
    top_plates: list[StatsPlateRow]
    top_people: list[StatsPersonRow]


class CPOStatsResponse(BaseModel):
    recent_sessions: list[StatsSessionRow]   # up to 5, most recent first
    menus: list[MenuStats]
    total_sessions: int
    distinct_members: int
    distinct_plates: int
    stats_reset_at: datetime | None = None


# ---------------------------------------------------------------------------
# API — CPO / team members & invites (self-service)
# ---------------------------------------------------------------------------

class TeamInviteResponse(BaseModel):
    id: str
    token: str
    created_at: datetime
    expires_at: datetime


# ---------------------------------------------------------------------------
# API — join a team (no auth, invite-link signup)
# ---------------------------------------------------------------------------

class JoinInfoResponse(BaseModel):
    team_name: str


class JoinTeamRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    email: EmailStr
    password: str = Field(min_length=8, max_length=1024)


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
    member_identifier: Literal["name", "email"] = "name"


class UpdateCurrencyRequest(BaseModel):
    currency: str = Field(min_length=1, max_length=10)


class UpdateTeamNameRequest(BaseModel):
    team_name: str = Field(min_length=1, max_length=128)


class UpdateMemberIdentifierRequest(BaseModel):
    member_identifier: Literal["name", "email"]


class UpdateDefaultGracePeriodRequest(BaseModel):
    default_grace_period_minutes: int = Field(ge=0)


class UpdateLanguageRequest(BaseModel):
    """Explicit null clears the preference ("follow the browser"); an
    unsupported tag is rejected with 422 by the Literal."""
    language: Language | None


class OrderItem(BaseModel):
    # 254 = RFC 5321 max address length. The per-mode cap (100 for names,
    # 254 for emails) is enforced in order_service — the only layer that
    # knows which mode the team link's CPO is in.
    member_name: str = Field(min_length=1, max_length=254)
    pizza_id: str
    comment: Annotated[str, Field(min_length=1, max_length=100)] | None = None


class SubmitOrderRequest(BaseModel):
    items: list[OrderItem] = Field(min_length=1, max_length=50)


class SubmitOrderResponse(BaseModel):
    status: str = "submitted"
    orders_created: int
    order_ids: list[str]
