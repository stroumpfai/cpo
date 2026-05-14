from fastapi import APIRouter, HTTPException, status

from models import LoginRequest, LoginResponse
from security import create_token
from storage import load_config
from utils import verify_password

router = APIRouter(tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest):
    cfg = load_config()

    # Check admin first
    if body.username == cfg.admin.username:
        if not verify_password(body.password, cfg.admin.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        token = create_token(user_id="admin", role="admin")
        return LoginResponse(token=token, role="admin")

    # Check CPO accounts
    cpo = next((c for c in cfg.cpos if c.username == body.username), None)
    if cpo is None or not verify_password(body.password, cpo.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_token(user_id=cpo.id, role="cpo")
    return LoginResponse(token=token, role="cpo")


@router.post("/logout")
def logout():
    # Stateless JWT — client is responsible for discarding the token
    return {"message": "Logged out"}
