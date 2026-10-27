"""Request/response models for services and retainers."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, Field

from app.modules.tasks.schemas import TaskItem, UserRef

ServiceKind = Literal["retainer", "project"]
ServiceStatus = Literal["planned", "active", "paused", "completed", "cancelled"]
TemplatePhase = Literal["setup", "monthly", "delivery"]
TeamArea = Literal[
    "account",
    "project_management",
    "seo",
    "content",
    "design",
    "development",
    "social",
    "analytics",
]


def _strip(value: object) -> object:
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


Text = Annotated[str | None, BeforeValidator(_strip)]
Fee = Annotated[Decimal | None, Field(default=None, ge=0, max_digits=14, decimal_places=2)]


class Ref(BaseModel):
    id: uuid.UUID
    name: str


class ServiceTypeOut(BaseModel):
    id: uuid.UUID
    key: str
    name: str
    kind: ServiceKind
    department: Ref | None
    is_active: bool


class ServiceSelection(BaseModel):
    """A service chosen for a client (at creation, or added later)."""

    service_key: str = Field(min_length=1, max_length=40)
    #: Monthly fee for retainers, the fixed price for projects.
    fee: Fee = None
    notes: Text = Field(default=None, max_length=500)


class AddServices(BaseModel):
    services: list[ServiceSelection] = Field(min_length=1, max_length=10)


class ProjectRef(BaseModel):
    id: uuid.UUID
    code: str
    name: str


class ClientRef(BaseModel):
    id: uuid.UUID
    code: str
    name: str


class Progress(BaseModel):
    total: int
    done: int


class ServiceItem(BaseModel):
    id: uuid.UUID
    code: str
    client: ClientRef
    service: ServiceTypeOut
    status: ServiceStatus
    status_label: str
    #: None when the viewer may not see money.
    fee: Decimal | None
    currency: str
    start_date: date | None
    end_date: date | None
    manager: UserRef | None
    project: ProjectRef | None
    #: Retainers: this month's tasks. Projects: every delivery task.
    progress: Progress


class ServicesTiles(BaseModel):
    active_retainers: int
    projects_in_progress: int
    planned: int
    #: Sum of active retainer fees; None when the viewer may not see money.
    contracted_monthly: Decimal | None


class ServicesOverview(BaseModel):
    tiles: ServicesTiles
    items: list[ServiceItem]


class MonthSummary(BaseModel):
    period: str
    total: int
    done: int


class ServicePermissions(BaseModel):
    manage: bool
    generate: bool
    see_money: bool


class ServiceDetail(ServiceItem):
    notes: str | None
    created_at: datetime
    onboarding_completed: bool
    #: YYYY-MM of the current month (retainers).
    current_period: str | None
    #: Retainers: this month's generated tasks. Projects: the delivery project's tasks.
    tasks: list[TaskItem]
    #: Retainers: per month, newest first.
    history: list[MonthSummary]
    permissions: ServicePermissions


class StartOptions(BaseModel):
    default_manager: UserRef | None
    managers: list[UserRef]
    onboarding_completed: bool


class StartService(BaseModel):
    manager_id: uuid.UUID
    start_date: date


class GenerateResult(BaseModel):
    period: str
    created: int
    skipped: int


class TemplateTaskOut(BaseModel):
    id: uuid.UUID
    phase: TemplatePhase
    title: str
    day_of_month: int | None
    start_offset_days: int
    duration_days: int
    requires_review: bool
    requires_client_approval: bool
    area: TeamArea | None
    sort: int


class TemplateTaskIn(BaseModel):
    #: Existing task to update; omit to add a new one.
    id: uuid.UUID | None = None
    phase: TemplatePhase
    title: Annotated[str, BeforeValidator(_strip)] = Field(min_length=1, max_length=200)
    day_of_month: int | None = Field(default=None, ge=1, le=28)
    start_offset_days: int = Field(default=0, ge=0, le=730)
    duration_days: int = Field(default=0, ge=0, le=365)
    requires_review: bool = True
    requires_client_approval: bool = False
    area: TeamArea | None = None


class TemplateUpdate(BaseModel):
    """The complete template: tasks not listed are retired (kept for history)."""

    tasks: list[TemplateTaskIn] = Field(max_length=60)


class ServiceTemplates(BaseModel):
    service: ServiceTypeOut
    tasks: list[TemplateTaskOut]
    can_edit: bool
