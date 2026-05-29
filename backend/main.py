import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.middleware.base import BaseHTTPMiddleware

from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from routers import admin, auth, cpo, orders

logger = logging.getLogger("uvicorn.error")

_version = os.getenv("CPO_VERSION", "dev")
_commit  = os.getenv("CPO_COMMIT",  "unknown")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("CPO %s — %s", _version, _commit)
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


app.add_middleware(_SecurityHeadersMiddleware)

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

app.include_router(auth.router, prefix="/api/auth")
app.include_router(admin.router, prefix="/api/admin")
app.include_router(cpo.router, prefix="/api/cpo")
app.include_router(orders.router, prefix="/api/orders")


@app.get("/api/health")
def health():
    return {"status": "ok"}


# Serve React frontend (after build)
frontend_dist = os.path.join(os.path.dirname(__file__), "dist")
if os.path.isdir(frontend_dist):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_spa(full_path: str):
        return FileResponse(os.path.join(frontend_dist, "index.html"))
