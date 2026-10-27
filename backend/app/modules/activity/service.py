"""Activity log (clickable demo): every client-timeline event the viewer may see.

Rules (demo; TODO(pilot-port): confirm the pilot has /activity)
- newest first; each entry shows the text, the actor ("System" when none) and the time;
- scoped to clients the viewer can see (ClientScope; `clients.view_all` sees all);
- filters: client, person, area (clients / onboarding / projects & tasks / approvals /
  documents / meetings / services), date range; keyset pagination (`before`);
- organisation and HR changes are in their own audit logs, not here.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.actor import Actor
from app.core.clock import Clock
from app.core.errors import ValidationFailed
from app.modules.activity.repository import ActivityRepository, area_of
from app.modules.activity.schemas import ActivityClient, ActivityItem, ActivityPage, ActivityPerson

MAX_LIMIT = 200


def _cursor(value: str | None) -> tuple[datetime, uuid.UUID] | None:
    if not value:
        return None
    try:
        stamp, _, ident = value.partition("|")
        return datetime.fromisoformat(stamp), uuid.UUID(ident)
    except ValueError as exc:
        raise ValidationFailed("That page cursor isn't valid. Reload the activity log.") from exc


class ActivityService:
    def __init__(self, session: AsyncSession, *, clock: Clock) -> None:
        self._repo = ActivityRepository(session)
        self._clock = clock

    async def page(
        self,
        actor: Actor,
        *,
        limit: int = 50,
        client_id: uuid.UUID | None = None,
        actor_id: uuid.UUID | None = None,
        area: str | None = None,
        since: date | None = None,
        until: date | None = None,
        before: str | None = None,
    ) -> ActivityPage:
        limit = max(1, min(limit, MAX_LIMIT))
        tz = self._clock.now().tzinfo
        rows = await self._repo.page(
            actor,
            limit=limit + 1,
            client_id=client_id,
            actor_id=actor_id,
            area=area,
            since=datetime.combine(since, time.min, tz) if since else None,
            until=datetime.combine(until + timedelta(days=1), time.min, tz) if until else None,
            before=_cursor(before),
        )
        more = len(rows) > limit
        rows = rows[:limit]
        last = rows[-1][0] if rows else None
        return ActivityPage(
            items=[
                ActivityItem(
                    id=event.id,
                    occurred_at=event.occurred_at,
                    verb=event.verb,
                    area=area_of(event.verb),  # type: ignore[arg-type]
                    summary=event.summary,
                    actor=ActivityPerson(id=user.id, full_name=user.full_name) if user else None,
                    client=ActivityClient(id=client.id, code=client.code, name=client.name),
                )
                for event, client, user in rows
            ],
            next_before=f"{last.occurred_at.isoformat()}|{last.id}" if more and last else None,
            people=[
                ActivityPerson(id=u.id, full_name=u.full_name)
                for u in await self._repo.people(actor)
            ],
        )
