"""
JWT creation / validation and FastAPI auth dependencies.

JWT payload shape: { "sub": "<user_id>", "role": "admin|cpo", "exp": <timestamp> }
"""
from __future__ import annotations

import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal

import jwt
from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config import JWT_ALGORITHM, JWT_EXPIRY_DAYS, JWT_SECRET

# ---------------------------------------------------------------------------
# Short-lived SSE tokens (replace full JWT in EventSource query strings)
# ---------------------------------------------------------------------------

_SSE_TOKEN_TTL = 60  # seconds — enough for the browser to open the connection
_sse_tokens: dict[str, tuple[str, float]] = {}  # token -> (user_id, monotonic expiry)


def issue_sse_token(user_id: str) -> str:
    """Create a one-time SSE token valid for _SSE_TOKEN_TTL seconds."""
    _evict_sse_tokens()
    token = secrets.token_urlsafe(32)
    _sse_tokens[token] = (user_id, time.monotonic() + _SSE_TOKEN_TTL)
    return token


def _evict_sse_tokens() -> None:
    now = time.monotonic()
    expired = [t for t, (_, exp) in _sse_tokens.items() if now > exp]
    for t in expired:
        del _sse_tokens[t]


def _consume_sse_token(token: str) -> str:
    """Validate and delete the token, returning user_id. Raises 401 on failure."""
    _evict_sse_tokens()
    entry = _sse_tokens.pop(token, None)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired SSE token")
    user_id, exp = entry
    if time.monotonic() > exp:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired SSE token")
    return user_id

_bearer          = HTTPBearer(auto_error=True)
_bearer_optional = HTTPBearer(auto_error=False)   # for SSE (no custom headers in EventSource)


# ---------------------------------------------------------------------------
# Token creation
# ---------------------------------------------------------------------------

def create_token(user_id: str, role: Literal["admin", "cpo"], version: int = 0) -> str:
    exp = datetime.now(tz=timezone.utc) + timedelta(days=JWT_EXPIRY_DAYS)
    payload = {"sub": user_id, "role": role, "exp": exp, "ver": version}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


# ---------------------------------------------------------------------------
# Token decoding
# ---------------------------------------------------------------------------

def _decode(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------

class CurrentUser:
    __slots__ = ("user_id", "role", "version")

    def __init__(self, user_id: str, role: str, version: int = 0) -> None:
        self.user_id = user_id
        self.role = role
        self.version = version


def get_current_user(
    creds: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> CurrentUser:
    payload = _decode(creds.credentials)
    return CurrentUser(user_id=payload["sub"], role=payload["role"], version=payload.get("ver", 0))


def require_admin(user: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


def require_cpo(user: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
    if user.role != "cpo":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CPO access required")
    from storage import load_config
    cfg = load_config()
    cpo = next((c for c in cfg.cpos if c.id == user.user_id), None)
    if cpo is None or cpo.token_version != user.version:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked")
    return user


def require_cpo_sse(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_optional)],
    token: Annotated[str | None, Query()] = None,
) -> CurrentUser:
    """Accepts a short-lived SSE token (?token=) or a Bearer JWT (fallback for non-browser clients)."""
    if token:
        user_id = _consume_sse_token(token)
        return CurrentUser(user_id=user_id, role="cpo")
    if creds:
        payload = _decode(creds.credentials)
        user = CurrentUser(user_id=payload["sub"], role=payload["role"])
        if user.role != "cpo":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CPO access required")
        return user
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
