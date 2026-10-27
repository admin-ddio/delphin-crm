"""HTTP surface of the activity log."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.dependencies import CurrentActor
from app.core.clock import Clock, get_clock
from app.core.errors import AUTH_ERROR_RESPONSES
from app.db.session import get_session
from app.modules.activity.schemas import ActivityArea, ActivityPage
from app.modules.activity.service import ActivityService

TAG = {"name": "activity", "description": "Organisation-wide activity log"}

router = APIRouter(prefix="/activity", tags=["activity"])


def get_activity_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> ActivityService:
    return ActivityService(session, clock=clock)


@router.get("", response_model=ActivityPage, responses=AUTH_ERROR_RESPONSES)
async def activity_log(
    *,
    actor: CurrentActor,
    service: Annotated[ActivityService, Depends(get_activity_service)],
    client_id: Annotated[uuid.UUID | None, Query()] = None,
    person_id: Annotated[uuid.UUID | None, Query(description="Who did it")] = None,
    area: Annotated[ActivityArea | None, Query()] = None,
    since: Annotated[date | None, Query()] = None,
    until: Annotated[date | None, Query()] = None,
    before: Annotated[str | None, Query(max_length=100, description="Cursor")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> ActivityPage:
    """Newest first, for clients the viewer can see."""
    return await service.page(
        actor,
        limit=limit,
        client_id=client_id,
        actor_id=person_id,
        area=area,
        since=since,
        until=until,
        before=before,
    )
