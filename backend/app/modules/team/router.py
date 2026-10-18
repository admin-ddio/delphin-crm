"""HTTP surface of the team module. So far: approving self sign-ups."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.actor import Actor
from app.authz.dependencies import require_permission
from app.authz.permissions import USERS_APPROVE
from app.core.clock import Clock, get_clock
from app.core.errors import AUTH_ERROR_RESPONSES, ErrorEnvelope
from app.db.session import get_session
from app.modules.team.schemas import ApproveRegistrationRequest, PendingRegistration
from app.modules.team.service import TeamService
from app.platform.identity.firebase import IdentityProvider, get_identity_provider

TAG = {"name": "team", "description": "Team & Employees, teams, workload, sign-up approvals"}

router = APIRouter(prefix="/team", tags=["team"])

Approver = Annotated[Actor, Depends(require_permission(USERS_APPROVE))]
NOT_PENDING: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorEnvelope, "description": "Not pending (or already handled)"}
}


def get_team_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    clock: Annotated[Clock, Depends(get_clock)],
    identity: Annotated[IdentityProvider, Depends(get_identity_provider)],
) -> TeamService:
    return TeamService(session, clock=clock, identity=identity)


Service = Annotated[TeamService, Depends(get_team_service)]


@router.get(
    "/registrations", response_model=list[PendingRegistration], responses=AUTH_ERROR_RESPONSES
)
async def list_pending_registrations(
    actor: Approver, service: Service
) -> list[PendingRegistration]:
    """Self sign-ups waiting for approval, oldest first."""
    return await service.pending_registrations()


@router.post(
    "/registrations/{user_id}/approve",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses={**AUTH_ERROR_RESPONSES, **NOT_PENDING},
)
async def approve_registration(
    user_id: uuid.UUID, body: ApproveRegistrationRequest, actor: Approver, service: Service
) -> None:
    await service.approve(actor, user_id, body.role)


@router.post(
    "/registrations/{user_id}/reject",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses={**AUTH_ERROR_RESPONSES, **NOT_PENDING},
)
async def reject_registration(user_id: uuid.UUID, actor: Approver, service: Service) -> None:
    await service.reject(actor, user_id)
