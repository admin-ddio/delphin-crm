"""In-app notifications (the bell). Implements app.platform.notifications.Notifier.

Other modules call notify()/notify_many() for pending actions; the recipient sees
them in the top bar. Nobody is notified about their own action. E-mail delivery is
not configured yet (TODO: a channel per notification_preferences).
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.actor import Actor
from app.core.errors import NotFound
from app.modules.notifications.repository import NotificationRepository
from app.modules.notifications.schemas import NotificationList, NotificationOut
from app.platform.notifications.interfaces import NotificationRequest
from app.platform.notifications.models import Notification


class NotificationService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = NotificationRepository(session)

    # ------------------------------------------------------------ delivery

    async def notify(self, request: NotificationRequest, *, at: datetime | None = None) -> None:
        notification = Notification(
            user_id=request.user_id,
            kind=request.kind,
            title=request.title[:200],
            body=request.body,
            link=request.link,
            entity_type=request.entity_type,
            entity_id=request.entity_id,
        )
        if at is not None:  # reminders use the job's clock (see notify_once_a_day)
            notification.created_at = at
        self._repo.add(notification)
        await self._repo.flush()

    async def notify_many(
        self,
        user_ids: Iterable[uuid.UUID | None],
        request: NotificationRequest,
        *,
        exclude: uuid.UUID | None = None,
    ) -> None:
        """One notification per distinct recipient, skipping the person who acted."""
        for user_id in dict.fromkeys(u for u in user_ids if u and u != exclude):
            await self.notify(
                NotificationRequest(
                    user_id=user_id,
                    kind=request.kind,
                    title=request.title,
                    body=request.body,
                    link=request.link,
                    entity_type=request.entity_type,
                    entity_id=request.entity_id,
                )
            )

    async def notify_once_a_day(self, request: NotificationRequest, now: datetime) -> bool:
        """Reminders: at most one per recipient, kind and entity every 24 hours."""
        if await self._repo.sent_since(
            request.user_id, request.kind, request.entity_id, now - timedelta(days=1)
        ):
            return False
        await self.notify(request, at=now)
        return True

    # ------------------------------------------------------------ the bell

    async def mine(self, actor: Actor, *, limit: int = 30) -> NotificationList:
        rows = await self._repo.recent(actor.user_id, limit=limit)
        return NotificationList(
            unread=await self._repo.unread_count(actor.user_id),
            items=[
                NotificationOut(
                    id=n.id,
                    kind=n.kind,
                    title=n.title,
                    body=n.body,
                    link=n.link,
                    created_at=n.created_at,
                    read=n.read_at is not None,
                )
                for n in rows
            ],
        )

    async def mark_read(self, actor: Actor, notification_id: uuid.UUID) -> NotificationList:
        if not await self._repo.mark_read(actor.user_id, notification_id, datetime.now(UTC)):
            current = await self.mine(actor)
            if not any(n.id == notification_id for n in current.items):
                raise NotFound("This notification doesn't exist.")
            return current
        return await self.mine(actor)

    async def mark_all_read(self, actor: Actor) -> NotificationList:
        await self._repo.mark_all_read(actor.user_id, datetime.now(UTC))
        return await self.mine(actor)
