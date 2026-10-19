"""HTTP surface of the approvals module. Mutations return the task's full TaskDetail."""

from __future__ import annotations

import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.dependencies import CurrentActor
from app.core.clock import Clock, get_clock
from app.core.errors import AUTH_ERROR_RESPONSES, ErrorEnvelope
from app.db.session import get_session
from app.modules.approvals.schemas import ApprovalItem, DecisionIn, SubmitIn
from app.modules.approvals.service import ApprovalService
from app.modules.tasks.schemas import TaskDetail

TAG = {"name": "approvals", "description": "Internal and client approvals"}

router = APIRouter(prefix="/approvals", tags=["approvals"])

ERRORS: dict[int | str, dict[str, Any]] = {
    **AUTH_ERROR_RESPONSES,
    404: {"model": ErrorEnvelope, "description": "Not found, or outside your access"},
    422: {"model": ErrorEnvelope, "description": "Validation failed or business rule violated"},
}


def get_approval_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> ApprovalService:
    return ApprovalService(session, clock=clock)


Service = Annotated[ApprovalService, Depends(get_approval_service)]


@router.get("", response_model=list[ApprovalItem], responses=AUTH_ERROR_RESPONSES)
async def list_approvals(
    actor: CurrentActor,
    service: Service,
    view: Annotated[Literal["mine", "all"], Query()] = "all",
) -> list[ApprovalItem]:
    """`mine`: open requests waiting for my decision. `all`: every visible request, newest first."""
    return await service.list_approvals(actor, view)


@router.post(
    "/submit", status_code=status.HTTP_201_CREATED, response_model=TaskDetail, responses=ERRORS
)
async def submit_for_review(body: SubmitIn, actor: CurrentActor, service: Service) -> TaskDetail:
    """Submit a new version of an in-progress task for internal review or client approval."""
    return await service.submit(actor, body)


@router.get("/{approval_id}", response_model=ApprovalItem, responses=ERRORS)
async def get_approval(
    approval_id: uuid.UUID, actor: CurrentActor, service: Service
) -> ApprovalItem:
    return await service.get(actor, approval_id)


@router.post("/{approval_id}/decision", response_model=TaskDetail, responses=ERRORS)
async def decide(
    approval_id: uuid.UUID, body: DecisionIn, actor: CurrentActor, service: Service
) -> TaskDetail:
    """Approve or request changes. Client-stage decisions record who decided and how."""
    return await service.decide(actor, approval_id, body)
