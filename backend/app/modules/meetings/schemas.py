"""Request/response models for the meetings module."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, EmailStr, Field, model_validator

MeetingType = Literal["kickoff", "review", "planning", "internal", "reporting", "other"]
MeetingStatus = Literal["scheduled", "completed", "cancelled"]
Platform = Literal["google_meet", "zoom", "teams", "phone", "in_person", "other"]


def _strip(value: object) -> object:
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


Text = Annotated[str | None, BeforeValidator(_strip)]


class UserRef(BaseModel):
    id: uuid.UUID
    full_name: str


class GuestIn(BaseModel):
    name: Annotated[str, BeforeValidator(_strip)] = Field(min_length=1, max_length=200)
    email: EmailStr | None = None
    organisation: Text = Field(default=None, max_length=200)


class AttendeeOut(BaseModel):
    id: uuid.UUID
    user: UserRef | None
    name: str
    email: str | None
    organisation: str | None
    external: bool


class ActionItemOut(BaseModel):
    id: uuid.UUID
    title: str
    owner: UserRef | None
    due_date: date | None
    done: bool


class MeetingOut(BaseModel):
    id: uuid.UUID
    client_id: uuid.UUID
    client_name: str
    title: str
    description: str | None
    type: MeetingType
    #: scheduled | completed | cancelled, plus `upcoming` / `awaiting_notes` for scheduled ones.
    status: MeetingStatus
    display_status: Literal["upcoming", "awaiting_notes", "completed", "cancelled"]
    starts_at: datetime
    ends_at: datetime
    platform: Platform | None
    location: str | None
    agenda: str | None
    notes: str | None
    attendees: list[AttendeeOut]
    action_items: list[ActionItemOut]
    completed_at: datetime | None
    cancelled_reason: str | None
    can_manage: bool


class MeetingStats(BaseModel):
    total: int
    completed: int
    upcoming: int
    cancelled: int


class ClientMeetings(BaseModel):
    stats: MeetingStats
    meetings: list[MeetingOut]
    can_schedule: bool


class _Times(BaseModel):
    @model_validator(mode="after")
    def _end_after_start(self) -> _Times:
        start, end = getattr(self, "starts_at", None), getattr(self, "ends_at", None)
        if start and end and end <= start:
            msg = "The meeting must end after it starts."
            raise ValueError(msg)
        return self


class MeetingIn(_Times):
    client_id: uuid.UUID
    title: Annotated[str, BeforeValidator(_strip)] = Field(min_length=1, max_length=200)
    description: Text = Field(default=None, max_length=300)
    type: MeetingType
    starts_at: datetime
    ends_at: datetime
    platform: Platform | None = None
    location: Text = Field(default=None, max_length=500, description="Link or address")
    agenda: Text = Field(default=None, max_length=4000)
    attendee_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)
    guests: list[GuestIn] = Field(default_factory=list, max_length=50)


class MeetingUpdate(_Times):
    title: Text = Field(default=None, max_length=200)
    description: Text = Field(default=None, max_length=300)
    type: MeetingType | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    platform: Platform | None = None
    location: Text = Field(default=None, max_length=500)
    agenda: Text = Field(default=None, max_length=4000)
    notes: Text = Field(default=None, max_length=8000)
    attendee_ids: list[uuid.UUID] | None = Field(default=None, max_length=50)
    guests: list[GuestIn] | None = Field(default=None, max_length=50)


class CompleteIn(BaseModel):
    notes: Annotated[str, BeforeValidator(_strip)] = Field(min_length=1, max_length=8000)


class CancelIn(BaseModel):
    reason: Text = Field(default=None, max_length=300)


class ActionItemIn(BaseModel):
    title: Annotated[str, BeforeValidator(_strip)] = Field(min_length=1, max_length=300)
    owner_id: uuid.UUID | None = None
    due_date: date | None = None


class ActionItemUpdate(BaseModel):
    title: Text = Field(default=None, max_length=300)
    owner_id: uuid.UUID | None = None
    due_date: date | None = None
    done: bool | None = None
