"""HTTP surface of the tasks module."""

from __future__ import annotations

import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.actor import Actor
from app.authz.dependencies import CurrentActor, require_permission
from app.authz.permissions import TASKS_CREATE
from app.core.clock import Clock, get_clock
from app.core.errors import AUTH_ERROR_RESPONSES, ErrorEnvelope
from app.db.session import get_session
from app.modules.tasks.schemas import (
    StatusChange,
    TaskCreate,
    TaskDetail,
    TaskItem,
    TaskUpdate,
    UserRef,
)
from app.modules.tasks.service import TaskService

TAG = {"name": "tasks", "description": "Tasks, versions and review"}

router = APIRouter(prefix="/tasks", tags=["tasks"])

ERRORS: dict[int | str, dict[str, Any]] = {
    **AUTH_ERROR_RESPONSES,
    404: {"model": ErrorEnvelope, "description": "Not found, or outside your access"},
    422: {"model": ErrorEnvelope, "description": "Validation failed or business rule violated"},
}


def get_task_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> TaskService:
    return TaskService(session, clock=clock)


Service = Annotated[TaskService, Depends(get_task_service)]


@router.get("", response_model=list[TaskItem], responses=AUTH_ERROR_RESPONSES)
async def list_tasks(
    actor: CurrentActor,
    service: Service,
    view: Annotated[Literal["mine", "review", "all"], Query()] = "mine",
    open_only: Annotated[bool, Query()] = True,
    assignee_id: Annotated[uuid.UUID | None, Query(description="With view=all")] = None,
) -> list[TaskItem]:
    """Assigned to me (default), awaiting my internal review, or every visible task
    (optionally one person's, e.g. an employee profile's workload)."""
    return await service.list_tasks(actor, view=view, open_only=open_only, assignee_id=assignee_id)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=TaskDetail, responses=ERRORS)
async def create_task(
    body: TaskCreate,
    actor: Annotated[Actor, Depends(require_permission(TASKS_CREATE))],
    service: Service,
) -> TaskDetail:
    return await service.create(actor, body)


@router.get("/assignee-options", response_model=list[UserRef], responses=AUTH_ERROR_RESPONSES)
async def assignee_options(
    actor: Annotated[Actor, Depends(require_permission(TASKS_CREATE))], service: Service
) -> list[UserRef]:
    """Active team members a task can be assigned to."""
    return await service.assignee_options()


@router.get("/{task_id}", response_model=TaskDetail, responses=ERRORS)
async def get_task(task_id: uuid.UUID, actor: CurrentActor, service: Service) -> TaskDetail:
    return await service.get(actor, task_id)


@router.patch("/{task_id}", response_model=TaskDetail, responses=ERRORS)
async def update_task(
    task_id: uuid.UUID, body: TaskUpdate, actor: CurrentActor, service: Service
) -> TaskDetail:
    """Title, description, assignee, due date. Project manager or team lead only."""
    return await service.update(actor, task_id, body)


@router.post("/{task_id}/status", response_model=TaskDetail, responses=ERRORS)
async def change_status(
    task_id: uuid.UUID, body: StatusChange, actor: CurrentActor, service: Service
) -> TaskDetail:
    """Move the task on the board; see TaskDetail.permissions.next_statuses."""
    return await service.change_status(actor, task_id, body)
