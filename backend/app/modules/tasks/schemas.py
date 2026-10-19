"""Request/response models for the tasks module."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, Field

TaskStatus = Literal[
    "backlog",
    "ready",
    "in_progress",
    "blocked",
    "internal_review",
    "client_approval",
    "completed",
    "cancelled",
]


def _strip(value: object) -> object:
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


class UserRef(BaseModel):
    id: uuid.UUID
    full_name: str


class TaskItem(BaseModel):
    id: uuid.UUID
    number: int
    code: str
    title: str
    status: TaskStatus
    status_label: str
    project_id: uuid.UUID
    project_name: str
    client_id: uuid.UUID
    client_name: str
    assignee: UserRef | None
    due_date: date | None
    overdue: bool
    requires_review: bool
    requires_client_approval: bool


class TaskPermissions(BaseModel):
    work: bool
    manage: bool
    #: Statuses this user may move the task to right now.
    next_statuses: list[TaskStatus]


class TaskDetail(TaskItem):
    description: str | None
    reviewer: UserRef | None
    created_at: datetime
    completed_at: datetime | None
    permissions: TaskPermissions


class TaskCreate(BaseModel):
    project_id: uuid.UUID
    title: Annotated[str, BeforeValidator(_strip)] = Field(min_length=1, max_length=200)
    description: Annotated[str | None, BeforeValidator(_strip)] = Field(
        default=None, max_length=4000
    )
    assignee_id: uuid.UUID | None = None
    due_date: date | None = None
    requires_review: bool = True
    requires_client_approval: bool = False


class TaskUpdate(BaseModel):
    title: Annotated[str | None, BeforeValidator(_strip)] = Field(
        default=None, min_length=1, max_length=200
    )
    description: Annotated[str | None, BeforeValidator(_strip)] = Field(
        default=None, max_length=4000
    )
    assignee_id: uuid.UUID | None = None
    due_date: date | None = None


class StatusChange(BaseModel):
    status: TaskStatus
