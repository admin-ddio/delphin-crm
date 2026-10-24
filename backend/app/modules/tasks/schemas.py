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
    #: May submit a new version for review now.
    submit: bool
    #: May decide the open approval now.
    decide: bool
    #: Why this user can't decide the open approval (e.g. they submitted it).
    decide_blocked: str | None


ApprovalStage = Literal["internal", "client"]
DecisionResult = Literal["approved", "changes"]


class FeedbackOut(BaseModel):
    stage: ApprovalStage
    result: DecisionResult
    #: Reviewer name, or "Name (client, via e-mail)".
    by: str
    note: str | None
    at: datetime


class VersionOut(BaseModel):
    number: int
    note: str
    link: str | None
    submitted_by: UserRef | None
    submitted_at: datetime
    feedback: list[FeedbackOut]


class OpenApproval(BaseModel):
    id: uuid.UUID
    stage: ApprovalStage
    version: int
    #: Internal: the reviewer. Client: the client's Account Manager (records the decision).
    approver: UserRef | None
    requested_by: UserRef | None
    created_at: datetime


class TaskDetail(TaskItem):
    description: str | None
    reviewer: UserRef | None
    created_at: datetime
    completed_at: datetime | None
    permissions: TaskPermissions
    versions: list[VersionOut]
    open_approval: OpenApproval | None
    #: Suggested client decision-maker (the client's primary contact).
    client_contact: str | None


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
    reviewer_id: uuid.UUID | None = None
    due_date: date | None = None


class StatusChange(BaseModel):
    status: TaskStatus
