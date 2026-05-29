import time

from fastapi import APIRouter, HTTPException, Request, status

from models import LoginRequest, LoginResponse
from security import create_token
from storage import load_config
from utils import hash_password, verify_password

router = APIRouter(tags=["auth"])

_DUMMY_HASH_CACHE: str | None = None


def _dummy_hash() -> str:
    global _DUMMY_HASH_CACHE
    if _DUMMY_HASH_CACHE is None:
        _DUMMY_HASH_CACHE = hash_password("__dummy_timing__")
    return _DUMMY_HASH_CACHE

_LOGIN_MAX_ATTEMPTS = 5
_LOGIN_WINDOW_SECONDS = 60

# {ip: [monotonic timestamps of recent attempts]}
_login_attempts: dict[str, list[float]] = {}


def clear_login_attempts() -> None:
    """Reset in-process login rate limit store (for tests)."""
    _login_attempts.clear()


def _check_login_rate_limit(ip: str) -> None:
    now = time.monotonic()
    cutoff = now - _LOGIN_WINDOW_SECONDS
    recent = [t for t in _login_attempts.get(ip, []) if t > cutoff]
    if len(recent) >= _LOGIN_MAX_ATTEMPTS:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many login attempts")
    _login_attempts[ip] = recent + [now]


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, request: Request):
    _check_login_rate_limit(request.client.host if request.client else "unknown")
    cfg = load_config()

    # Check admin first
    if body.username == cfg.admin.username:
        if not verify_password(body.password, cfg.admin.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        token = create_token(user_id="admin", role="admin")
        return LoginResponse(token=token, role="admin")

    # Check CPO accounts — always run verify_password to equalise timing (prevents username enumeration)
    cpo = next((c for c in cfg.cpos if c.username == body.username), None)
    hash_to_check = cpo.password_hash if cpo else _dummy_hash()
    if not verify_password(body.password, hash_to_check) or cpo is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_token(user_id=cpo.id, role="cpo", version=cpo.token_version)
    return LoginResponse(token=token, role="cpo")


@router.post("/logout")
def logout():
    # Stateless JWT — client is responsible for discarding the token
    return {"message": "Logged out"}
