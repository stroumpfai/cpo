"""
JWT creation / validation and FastAPI auth dependencies.

JWT payload shape: { "sub": "<user_id>", "role": "admin|cpo", "exp": <timestamp> }
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config import JWT_ALGORITHM, JWT_EXPIRY_DAYS, JWT_SECRET

_bearer = HTTPBearer(auto_error=True)


# ---------------------------------------------------------------------------
# Token creation
# ---------------------------------------------------------------------------

def create_token(user_id: str, role: Literal["admin", "cpo"]) -> str:
    exp = datetime.now(tz=timezone.utc) + timedelta(days=JWT_EXPIRY_DAYS)
    payload = {"sub": user_id, "role": role, "exp": exp}
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
    __slots__ = ("user_id", "role")

    def __init__(self, user_id: str, role: str) -> None:
        self.user_id = user_id
        self.role = role


def get_current_user(
    creds: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> CurrentUser:
    payload = _decode(creds.credentials)
    return CurrentUser(user_id=payload["sub"], role=payload["role"])


def require_admin(user: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


def require_cpo(user: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
    if user.role != "cpo":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CPO access required")
    return user
