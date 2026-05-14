from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from routers import admin, auth, cpo, orders

app = FastAPI(title="CPO - Chief Pizza Officer", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
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
