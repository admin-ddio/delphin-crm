"""HTTP surface of the notifications module: the signed-in user's bell."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.dependencies import CurrentActor
from app.core.errors import AUTH_ERROR_RESPONSES, ErrorEnvelope
from app.db.session import get_session
from app.modules.notifications.schemas import NotificationList
from app.modules.notifications.service import NotificationService

TAG = {"name": "notifications", "description": "In-app notifications and preferences"}

router = APIRouter(prefix="/notifications", tags=["notifications"])

NOT_FOUND: dict[int | str, dict[str, Any]] = {
    **AUTH_ERROR_RESPONSES,
    404: {"model": ErrorEnvelope, "description": "Not one of your notifications"},
}


def get_notification_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> NotificationService:
    return NotificationService(session)


Service = Annotated[NotificationService, Depends(get_notification_service)]


@router.get("", response_model=NotificationList, responses=AUTH_ERROR_RESPONSES)
async def my_notifications(actor: CurrentActor, service: Service) -> NotificationList:
    """My latest 30 notifications, newest first, with the unread count."""
    return await service.mine(actor)


@router.post("/{notification_id}/read", response_model=NotificationList, responses=NOT_FOUND)
async def mark_read(
    notification_id: uuid.UUID, actor: CurrentActor, service: Service
) -> NotificationList:
    return await service.mark_read(actor, notification_id)


@router.post("/read-all", response_model=NotificationList, responses=AUTH_ERROR_RESPONSES)
async def mark_all_read(actor: CurrentActor, service: Service) -> NotificationList:
    return await service.mark_all_read(actor)
