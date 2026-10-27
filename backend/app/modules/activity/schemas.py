"""Request/response models for the activity log."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

ActivityArea = Literal[
    "clients", "onboarding", "projects", "approvals", "documents", "meetings", "services", "other"
]


class ActivityPerson(BaseModel):
    id: uuid.UUID
    full_name: str


class ActivityClient(BaseModel):
    id: uuid.UUID
    code: str
    name: str


class ActivityItem(BaseModel):
    id: uuid.UUID
    occurred_at: datetime
    verb: str
    area: ActivityArea
    summary: str | None
    #: None for system events (scheduled jobs, the public questionnaire).
    actor: ActivityPerson | None
    client: ActivityClient


class ActivityPage(BaseModel):
    items: list[ActivityItem]
    #: Pass as `before` to load older entries; None at the end.
    next_before: str | None
    #: People who appear in the log the viewer can see (for the filter).
    people: list[ActivityPerson]
