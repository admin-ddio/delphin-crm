"""Request/response models for the team module."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class PendingRegistration(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    registered_at: datetime
    # None when the Firebase account no longer exists.
    email_verified: bool | None


class ApproveRegistrationRequest(BaseModel):
    role: str = Field(min_length=1, max_length=64)
