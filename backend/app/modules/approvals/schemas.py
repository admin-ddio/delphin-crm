"""Request/response models for the approvals module."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, Field, field_validator

from app.modules.tasks.schemas import ApprovalStage, DecisionResult, UserRef

ApprovalStatus = Literal["submitted", "approved", "changes", "cancelled"]
Channel = Literal["email", "call", "meeting", "whatsapp"]


def _strip(value: object) -> object:
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


Text = Annotated[str | None, BeforeValidator(_strip)]


class SubmitIn(BaseModel):
    task_id: uuid.UUID
    #: What changed / notes for the reviewer (required, demo).
    note: Text = Field(default=None, max_length=4000)
    link: Text = Field(default=None, max_length=500)

    @field_validator("link")
    @classmethod
    def _http_link(cls, value: str | None) -> str | None:
        if value is not None and not value.lower().startswith(("http://", "https://")):
            msg = "The link must start with http:// or https://"
            raise ValueError(msg)
        return value


class DecisionIn(BaseModel):
    decision: DecisionResult
    #: Required when requesting changes.
    note: Text = Field(default=None, max_length=4000)
    #: Client stage only: who at the client decided, and how they told us.
    client_decider: Text = Field(default=None, max_length=200)
    client_channel: Channel | None = None


class ApprovalItem(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    task_code: str
    task_title: str
    client_id: uuid.UUID
    client_name: str
    stage: ApprovalStage
    version: int
    status: ApprovalStatus
    approver: UserRef | None
    requested_by: UserRef | None
    created_at: datetime
    decided_at: datetime | None
