"""Queries for in-app notifications (table defined in app.platform.notifications.models)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.notifications.models import Notification


class NotificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def add(self, notification: Notification) -> None:
        self._session.add(notification)

    async def flush(self) -> None:
        await self._session.flush()

    async def recent(self, user_id: uuid.UUID, *, limit: int) -> list[Notification]:
        rows = await self._session.execute(
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc(), Notification.id)
            .limit(limit)
        )
        return list(rows.scalars())

    async def unread_count(self, user_id: uuid.UUID) -> int:
        stmt = select(func.count()).where(
            Notification.user_id == user_id, Notification.read_at.is_(None)
        )
        return int((await self._session.execute(stmt)).scalar_one())

    async def mark_read(self, user_id: uuid.UUID, notification_id: uuid.UUID, at: datetime) -> bool:
        result = await self._session.execute(
            update(Notification)
            .where(
                Notification.id == notification_id,
                Notification.user_id == user_id,
                Notification.read_at.is_(None),
            )
            .values(read_at=at)
        )
        return bool(result.rowcount)  # type: ignore[attr-defined]

    async def mark_all_read(self, user_id: uuid.UUID, at: datetime) -> int:
        result = await self._session.execute(
            update(Notification)
            .where(Notification.user_id == user_id, Notification.read_at.is_(None))
            .values(read_at=at)
        )
        return int(result.rowcount)  # type: ignore[attr-defined]

    async def sent_since(
        self, user_id: uuid.UUID, kind: str, entity_id: str | None, since: datetime
    ) -> bool:
        stmt = select(Notification.id).where(
            Notification.user_id == user_id,
            Notification.kind == kind,
            Notification.entity_id == entity_id,
            Notification.created_at >= since,
        )
        return (await self._session.execute(stmt.limit(1))).first() is not None
