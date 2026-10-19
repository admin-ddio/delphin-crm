"""HTTP surface of the projects module."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.actor import Actor
from app.authz.dependencies import CurrentActor, require_permission
from app.authz.permissions import PROJECTS_CREATE
from app.core.clock import Clock, get_clock
from app.core.errors import AUTH_ERROR_RESPONSES, ErrorEnvelope
from app.db.session import get_session
from app.modules.projects.schemas import (
    EligibleClient,
    ProjectCreate,
    ProjectDetail,
    ProjectListItem,
)
from app.modules.projects.service import ProjectService
from app.modules.tasks.schemas import UserRef

TAG = {"name": "projects", "description": "Projects and boards"}

router = APIRouter(prefix="/projects", tags=["projects"])

ERRORS: dict[int | str, dict[str, Any]] = {
    **AUTH_ERROR_RESPONSES,
    404: {"model": ErrorEnvelope, "description": "Not found, or outside your access"},
    422: {"model": ErrorEnvelope, "description": "Validation failed or business rule violated"},
}


def get_project_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> ProjectService:
    return ProjectService(session, clock=clock)


Service = Annotated[ProjectService, Depends(get_project_service)]
Creator = Annotated[Actor, Depends(require_permission(PROJECTS_CREATE))]


@router.get("", response_model=list[ProjectListItem], responses=AUTH_ERROR_RESPONSES)
async def list_projects(
    actor: CurrentActor,
    service: Service,
    client_id: Annotated[uuid.UUID | None, Query()] = None,
) -> list[ProjectListItem]:
    """Projects the actor may see, newest first, with task statistics."""
    return await service.list_projects(actor, client_id=client_id)


@router.post(
    "", status_code=status.HTTP_201_CREATED, response_model=ProjectDetail, responses=ERRORS
)
async def create_project(body: ProjectCreate, actor: Creator, service: Service) -> ProjectDetail:
    """Only for clients whose onboarding is completed; optionally seeds template tasks."""
    return await service.create(actor, body)


@router.get(
    "/eligible-clients", response_model=list[EligibleClient], responses=AUTH_ERROR_RESPONSES
)
async def eligible_clients(actor: Creator, service: Service) -> list[EligibleClient]:
    """Visible clients whose onboarding is completed."""
    return await service.eligible_clients(actor)


@router.get("/manager-options", response_model=list[UserRef], responses=AUTH_ERROR_RESPONSES)
async def manager_options(actor: Creator, service: Service) -> list[UserRef]:
    """People who can manage a project."""
    return await service.manager_options()


@router.get("/{project_id}", response_model=ProjectDetail, responses=ERRORS)
async def get_project(
    project_id: uuid.UUID, actor: CurrentActor, service: Service
) -> ProjectDetail:
    """The project with its stats and every task (the board)."""
    return await service.get(actor, project_id)
