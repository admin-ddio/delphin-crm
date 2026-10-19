"""HTTP surface of the meetings module. Mutations return the meeting's full MeetingOut."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.dependencies import CurrentActor
from app.core.clock import Clock, get_clock
from app.core.errors import AUTH_ERROR_RESPONSES, ErrorEnvelope
from app.db.session import get_session
from app.modules.meetings.schemas import (
    ActionItemIn,
    ActionItemUpdate,
    CancelIn,
    ClientMeetings,
    CompleteIn,
    MeetingIn,
    MeetingOut,
    MeetingUpdate,
)
from app.modules.meetings.service import MeetingService

TAG = {"name": "meetings", "description": "Client meetings, kickoffs, notes and action items"}

router = APIRouter(prefix="/meetings", tags=["meetings"])

ERRORS: dict[int | str, dict[str, Any]] = {
    **AUTH_ERROR_RESPONSES,
    404: {"model": ErrorEnvelope, "description": "Not found, or outside your access"},
    422: {"model": ErrorEnvelope, "description": "Validation failed or business rule violated"},
}


def get_meeting_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> MeetingService:
    return MeetingService(session, clock=clock)


Service = Annotated[MeetingService, Depends(get_meeting_service)]


@router.get("/clients/{client_id}", response_model=ClientMeetings, responses=ERRORS)
async def client_meetings(
    client_id: uuid.UUID, actor: CurrentActor, service: Service
) -> ClientMeetings:
    """Every meeting for the client (oldest first) with summary counts."""
    return await service.for_client(actor, client_id)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=MeetingOut, responses=ERRORS)
async def schedule_meeting(body: MeetingIn, actor: CurrentActor, service: Service) -> MeetingOut:
    return await service.schedule(actor, body)


@router.get("/{meeting_id}", response_model=MeetingOut, responses=ERRORS)
async def get_meeting(meeting_id: uuid.UUID, actor: CurrentActor, service: Service) -> MeetingOut:
    return await service.get(actor, meeting_id)


@router.patch("/{meeting_id}", response_model=MeetingOut, responses=ERRORS)
async def update_meeting(
    meeting_id: uuid.UUID, body: MeetingUpdate, actor: CurrentActor, service: Service
) -> MeetingOut:
    """Scheduled meetings only. Attendee lists given here replace the current ones."""
    return await service.update(actor, meeting_id, body)


@router.post("/{meeting_id}/complete", response_model=MeetingOut, responses=ERRORS)
async def complete_meeting(
    meeting_id: uuid.UUID, body: CompleteIn, actor: CurrentActor, service: Service
) -> MeetingOut:
    """Record the meeting notes and mark it completed."""
    return await service.complete(actor, meeting_id, body)


@router.post("/{meeting_id}/cancel", response_model=MeetingOut, responses=ERRORS)
async def cancel_meeting(
    meeting_id: uuid.UUID, body: CancelIn, actor: CurrentActor, service: Service
) -> MeetingOut:
    return await service.cancel(actor, meeting_id, body)


@router.post("/{meeting_id}/action-items", response_model=MeetingOut, responses=ERRORS)
async def add_action_item(
    meeting_id: uuid.UUID, body: ActionItemIn, actor: CurrentActor, service: Service
) -> MeetingOut:
    return await service.add_action_item(actor, meeting_id, body)


@router.patch("/action-items/{item_id}", response_model=MeetingOut, responses=ERRORS)
async def update_action_item(
    item_id: uuid.UUID, body: ActionItemUpdate, actor: CurrentActor, service: Service
) -> MeetingOut:
    """The item's owner may tick it off; managers may change anything."""
    return await service.update_action_item(actor, item_id, body)


@router.delete("/action-items/{item_id}", response_model=MeetingOut, responses=ERRORS)
async def delete_action_item(
    item_id: uuid.UUID, actor: CurrentActor, service: Service
) -> MeetingOut:
    return await service.delete_action_item(actor, item_id)
