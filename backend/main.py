import logging
import os
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import PlainTextResponse

from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from config import MAX_BODY_BYTES
from error_codes import AppError
from models import VersionResponse
from routers import admin, auth, cpo, join, orders
from security import CurrentUser, get_current_user

logger = logging.getLogger("uvicorn.error")

_version = os.getenv("CPO_VERSION", "dev")
_commit  = os.getenv("CPO_COMMIT",  "unknown")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("CPO %s — %s", _version, _commit)
    import db
    from json_migration import migrate_legacy_json_if_needed

    db.run_migrations()
    migrate_legacy_json_if_needed()
    if not _trusted_proxy:
        logger.warning(
            "TRUSTED_PROXY is not set — client IPs are taken from the TCP peer. "
            "If this app runs behind a reverse proxy, every request appears to come "
            "from the proxy: rate limits become global and order IP tracking is useless. "
            "Set TRUSTED_PROXY to the proxy address to enable X-Forwarded-For parsing."
        )
    yield


_debug = os.getenv("DEBUG", "false").lower() == "true"

app = FastAPI(
    title="CPO - Chief Pizza Officer",
    version=f"{_version} ({_commit})",
    lifespan=lifespan,
    docs_url="/docs" if _debug else None,
    redoc_url="/redoc" if _debug else None,
    openapi_url="/openapi.json" if _debug else None,
)

_CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "connect-src 'self'; "
    "img-src 'self' data:; "
    "font-src 'self'; "
    "form-action 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'"
)


class _SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = _CSP
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


class _BodySizeLimitMiddleware:
    """Reject request bodies above MAX_BODY_BYTES with 413.

    Declared Content-Length is checked up front; chunked bodies are counted as
    they stream (the HTTPException raised from receive() is turned into a 413
    by the app's exception middleware before any response has started).
    """

    def __init__(self, app, max_bytes: int = MAX_BODY_BYTES):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        for name, value in scope["headers"]:
            if name == b"content-length":
                try:
                    declared = int(value)
                except ValueError:
                    declared = 0
                if declared > self.max_bytes:
                    response = PlainTextResponse("Request body too large", status_code=413)
                    return await response(scope, receive, send)

        received = 0

        async def limited_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise HTTPException(status_code=413, detail="Request body too large")
            return message

        return await self.app(scope, limited_receive, send)


app.add_middleware(_SecurityHeadersMiddleware)
app.add_middleware(_BodySizeLimitMiddleware)

_trusted_proxy = [h.strip() for h in os.getenv("TRUSTED_PROXY", "").split(",") if h.strip()]
if _trusted_proxy:
    app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=_trusted_proxy)

_allowed_origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=bool(_allowed_origins),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(AppError)
async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    """Emit the English `detail` alongside the stable code and the values
    interpolated into it, so the client can re-render the message in the user's
    language. Plain HTTPExceptions (and FastAPI's own 422s) keep their default
    shape — Starlette picks this handler off AppError's MRO before the generic
    HTTPException one."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "code": exc.code, "params": exc.params},
        headers=exc.headers,
    )


app.include_router(auth.router, prefix="/api/auth")
app.include_router(admin.router, prefix="/api/admin")
app.include_router(cpo.router, prefix="/api/cpo")
app.include_router(join.router, prefix="/api/join")
app.include_router(orders.router, prefix="/api/orders")


@app.get("/api/health")
def health():
    return {"status": "ok"}


# Any signed-in user, admin or CPO — get_current_user validates the JWT
# without pinning a role, so one endpoint serves both dashboards. Kept behind
# auth so the commit SHA is not readable anonymously, matching the DEBUG gate
# on /docs and /openapi.json above.
@app.get("/api/version", response_model=VersionResponse)
def version(user: Annotated[CurrentUser, Depends(get_current_user)]):
    return VersionResponse(version=_version, commit=_commit)


# Serve React frontend (after build)
frontend_dist = os.path.join(os.path.dirname(__file__), "dist")
if os.path.isdir(frontend_dist):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_spa(full_path: str):
        return FileResponse(os.path.join(frontend_dist, "index.html"))
