"""Queries for meetings. A meeting is visible exactly when its client is (ClientScope)."""

from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.actor import Actor
from app.authz.scopes import apply_scope
from app.modules.clients.models import Client, ClientTeamMember
from app.modules.clients.repository import ClientScope
from app.modules.meetings.models import Meeting, MeetingActionItem, MeetingAttendee
from app.platform.identity.models import User


class MeetingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def visible_client(self, actor: Actor, client_id: uuid.UUID) -> Client | None:
        stmt = apply_scope(select(Client).where(Client.id == client_id), actor, ClientScope())
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def on_team(self, client_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        stmt = select(ClientTeamMember.user_id).where(
            ClientTeamMember.client_id == client_id, ClientTeamMember.user_id == user_id
        )
        return (await self._session.execute(stmt)).first() is not None

    async def for_client(self, client_id: uuid.UUID) -> list[Meeting]:
        rows = await self._session.execute(
            select(Meeting)
            .where(Meeting.client_id == client_id)
            .order_by(Meeting.starts_at, Meeting.id)
        )
        return list(rows.scalars())

    async def meeting(self, meeting_id: uuid.UUID, *, lock: bool = False) -> Meeting | None:
        stmt = select(Meeting).where(Meeting.id == meeting_id)
        if lock:
            stmt = stmt.with_for_update()
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def attendees(
        self, meeting_ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, list[tuple[MeetingAttendee, User | None]]]:
        out: dict[uuid.UUID, list[tuple[MeetingAttendee, User | None]]] = defaultdict(list)
        if not meeting_ids:
            return out
        rows = await self._session.execute(
            select(MeetingAttendee, User)
            .outerjoin(User, User.id == MeetingAttendee.user_id)
            .where(MeetingAttendee.meeting_id.in_(meeting_ids))
            .order_by(MeetingAttendee.user_id.is_(None), User.full_name, MeetingAttendee.name)
        )
        for attendee, user in rows.all():
            out[attendee.meeting_id].append((attendee, user))
        return out

    async def action_items(
        self, meeting_ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, list[tuple[MeetingActionItem, User | None]]]:
        out: dict[uuid.UUID, list[tuple[MeetingActionItem, User | None]]] = defaultdict(list)
        if not meeting_ids:
            return out
        rows = await self._session.execute(
            select(MeetingActionItem, User)
            .outerjoin(User, User.id == MeetingActionItem.owner_id)
            .where(MeetingActionItem.meeting_id.in_(meeting_ids))
            .order_by(MeetingActionItem.created_at, MeetingActionItem.id)
        )
        for item, user in rows.all():
            out[item.meeting_id].append((item, user))
        return out

    async def action_item(self, item_id: uuid.UUID) -> MeetingActionItem | None:
        return await self._session.get(MeetingActionItem, item_id)

    async def active_users(self, ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, User]:
        if not ids:
            return {}
        rows = await self._session.execute(
            select(User).where(
                User.id.in_(ids), User.is_active.is_(True), User.approved_at.is_not(None)
            )
        )
        return {user.id: user for user in rows.scalars()}

    async def replace_attendees(self, meeting_id: uuid.UUID, rows: list[MeetingAttendee]) -> None:
        await self._session.execute(
            delete(MeetingAttendee).where(MeetingAttendee.meeting_id == meeting_id)
        )
        self._session.add_all(rows)
        await self._session.flush()

    def add(self, obj: Meeting | MeetingAttendee | MeetingActionItem) -> None:
        self._session.add(obj)

    async def delete(self, obj: MeetingActionItem) -> None:
        await self._session.delete(obj)
        await self._session.flush()

    async def flush(self) -> None:
        await self._session.flush()
