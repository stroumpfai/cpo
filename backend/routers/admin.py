from typing import Annotated

from fastapi import APIRouter, Depends

from models import (
    AdminResponse,
    AdminTeamResponse,
    ChangePasswordRequest,
    CPOUsageStats,
    CreateAdminRequest,
    CreateCPORequest,
    ResetPasswordRequest,
    TeamMemberResponse,
    UpdateCPOEmailRequest,
    UpdateTeamNameRequest,
)
from security import CurrentUser, require_admin
from services import admin_service

router = APIRouter(tags=["admin"])

Admin = Annotated[CurrentUser, Depends(require_admin)]


@router.get("/cpos", response_model=list[AdminTeamResponse])
def list_cpos(user: Admin):
    return admin_service.list_cpos()


@router.get("/stats", response_model=list[CPOUsageStats])
def usage_stats(user: Admin):
    return admin_service.usage_stats()


@router.post("/cpos", response_model=AdminTeamResponse, status_code=201)
def create_cpo(body: CreateCPORequest, user: Admin):
    return admin_service.create_cpo(
        username=body.username,
        email=body.email,
        team_name=body.team_name,
        initial_password=body.initial_password,
    )


@router.put("/cpos/{cpo_id}", response_model=TeamMemberResponse)
def update_cpo_email(cpo_id: str, body: UpdateCPOEmailRequest, user: Admin):
    return admin_service.update_cpo_email(cpo_id, body.email)


@router.put("/teams/{team_id}", response_model=AdminTeamResponse)
def update_team_name(team_id: str, body: UpdateTeamNameRequest, user: Admin):
    return admin_service.update_team_name(team_id, body.team_name)


@router.delete("/cpos/{cpo_id}", status_code=204)
def delete_cpo(cpo_id: str, user: Admin):
    admin_service.delete_cpo(cpo_id)


@router.post("/cpos/{cpo_id}/reset-password", response_model=TeamMemberResponse)
def reset_password(cpo_id: str, body: ResetPasswordRequest, user: Admin):
    return admin_service.reset_password(cpo_id, body.new_password)


@router.get("/admins", response_model=list[AdminResponse])
def list_admins(user: Admin):
    return admin_service.list_admins(actor_id=int(user.user_id))


@router.post("/admins", response_model=AdminResponse, status_code=201)
def create_admin(body: CreateAdminRequest, user: Admin):
    return admin_service.create_admin(
        username=body.username,
        initial_password=body.initial_password,
    )


@router.delete("/admins/{admin_id}", status_code=204)
def delete_admin(admin_id: int, user: Admin):
    admin_service.delete_admin(actor_id=int(user.user_id), admin_id=admin_id)


@router.post("/admins/{admin_id}/reset-password", response_model=AdminResponse)
def reset_admin_password(admin_id: int, body: ResetPasswordRequest, user: Admin):
    return admin_service.reset_admin_password(
        actor_id=int(user.user_id), admin_id=admin_id, new_password=body.new_password
    )


@router.post("/change-password", status_code=204)
def change_admin_password(body: ChangePasswordRequest, user: Admin):
    admin_service.change_admin_password(
        admin_id=int(user.user_id),
        current_password=body.current_password,
        new_password=body.new_password,
    )
