"""Request/response models for the projects module."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, Field

from app.modules.tasks.schemas import TaskItem, UserRef


class ProjectStats(BaseModel):
    tasks: int
    open: int
    overdue: int
    in_review: int
    #: Completed ÷ non-cancelled tasks, 0–100 (demo rule).
    progress: int


class ProjectListItem(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    client_id: uuid.UUID
    client_name: str
    manager: UserRef
    start_date: date
    stats: ProjectStats


class ProjectDetail(ProjectListItem):
    template: str | None
    created_at: datetime
    tasks: list[TaskItem]
    can_create_tasks: bool


class ProjectCreate(BaseModel):
    client_id: uuid.UUID
    name: Annotated[str, BeforeValidator(lambda v: v.strip() if isinstance(v, str) else v)] = Field(
        min_length=1, max_length=200
    )
    manager_id: uuid.UUID
    start_date: date
    template: Literal["seo_foundation", "blank"] = "seo_foundation"


class EligibleClient(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    has_project: bool
