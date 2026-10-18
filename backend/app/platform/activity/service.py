"""Record activity events inside the caller's transaction."""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.activity.models import ActivityEvent
from app.platform.audit.service import redact


class ActivityRecorder:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(
        self,
        *,
        verb: str,
        subject_type: str,
        subject_id: str | uuid.UUID,
        actor_user_id: uuid.UUID | None = None,
        summary: str | None = None,
        context: Mapping[str, Any] | None = None,
    ) -> ActivityEvent:
        event = ActivityEvent(
            verb=verb,
            subject_type=subject_type,
            subject_id=str(subject_id),
            actor_user_id=actor_user_id,
            summary=summary,
            context=redact(dict(context or {})),
        )
        self._session.add(event)
        await self._session.flush()
        return event
