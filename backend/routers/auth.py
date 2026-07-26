import os
import time

from fastapi import APIRouter, HTTPException, Request, Response, status

from config import COOKIE_SECURE, JWT_EXPIRY_DAYS
from models import LoginRequest, LoginResponse
from security import AUTH_COOKIE_NAME, create_token
from storage import load_config
from utils import hash_password, verify_password

router = APIRouter(tags=["auth"])

_DUMMY_HASH_CACHE: str | None = None


def _dummy_hash() -> str:
    global _DUMMY_HASH_CACHE
    if _DUMMY_HASH_CACHE is None:
        _DUMMY_HASH_CACHE = hash_password("__dummy_timing__")
    return _DUMMY_HASH_CACHE

# Overridable for automated e2e runs, where every login comes from 127.0.0.1
# and a full suite exceeds the human-scale default within one window.
_LOGIN_MAX_ATTEMPTS = int(os.getenv("LOGIN_MAX_ATTEMPTS", "5"))
_LOGIN_WINDOW_SECONDS = 60

# {ip: [monotonic timestamps of recent attempts]}
_login_attempts: dict[str, list[float]] = {}


def clear_login_attempts() -> None:
    """Reset in-process login rate limit store (for tests)."""
    _login_attempts.clear()


def _check_login_rate_limit(ip: str) -> None:
    now = time.monotonic()
    cutoff = now - _LOGIN_WINDOW_SECONDS
    # Evict IPs whose window has expired to prevent unbounded growth
    stale = [i for i, ts in _login_attempts.items() if not ts or ts[-1] <= cutoff]
    for i in stale:
        del _login_attempts[i]
    recent = [t for t in _login_attempts.get(ip, []) if t > cutoff]
    if len(recent) >= _LOGIN_MAX_ATTEMPTS:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many login attempts")
    _login_attempts[ip] = recent + [now]


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        max_age=JWT_EXPIRY_DAYS * 86400,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="strict",
        path="/",
    )


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, request: Request, response: Response):
    _check_login_rate_limit(request.client.host if request.client else "unknown")
    cfg = load_config()

    # Admins take precedence over CPOs on username collision (creation rejects
    # cross-role duplicates). A single verify_password call always runs to
    # equalise timing (prevents username enumeration).
    admin = next((a for a in cfg.admins if a.username == body.username), None)
    cpo = None if admin else next((c for c in cfg.cpos if c.username == body.username), None)
    account = admin or cpo
    hash_to_check = account.password_hash if account else _dummy_hash()
    if not verify_password(body.password, hash_to_check) or account is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if admin is not None:
        token = create_token(user_id=str(admin.id), role="admin", version=admin.token_version)
        _set_auth_cookie(response, token)
        return LoginResponse(token=token, role="admin")

    token = create_token(user_id=cpo.id, role="cpo", version=cpo.token_version)
    _set_auth_cookie(response, token)
    return LoginResponse(token=token, role="cpo")


@router.post("/logout")
def logout(response: Response):
    # Clear the auth cookie; Bearer clients discard the token themselves
    response.delete_cookie(AUTH_COOKIE_NAME, path="/", httponly=True, secure=COOKIE_SECURE, samesite="strict")
    return {"message": "Logged out"}
