"""Client meetings: schedule, run, record notes and action items (product mockups).

Rules (TODO(pilot-port): confirm against the pilot)
- anyone who can see the client sees its meetings;
- schedule / edit / complete / cancel: the client's Account Manager, its team,
  Super Admin, or `meetings.manage` (AM, PM, Team Lead);
- completing needs meeting notes; a completed `kickoff` meeting completes
  onboarding step 9, a completed `internal` meeting (with a team) step 10;
- completed and cancelled meetings are read-only except for action items;
- internal attendees are notified when a meeting is scheduled, moved or cancelled;
- every change is audited and appears on the client's timeline.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.actor import Actor
from app.authz.permissions import MEETINGS_MANAGE
from app.core.clock import Clock
from app.core.errors import BusinessRuleViolation, Forbidden, NotFound, ValidationFailed
from app.modules.clients.models import Client
from app.modules.meetings.models import Meeting, MeetingActionItem, MeetingAttendee
from app.modules.meetings.repository import MeetingRepository
from app.modules.meetings.schemas import (
    ActionItemIn,
    ActionItemOut,
    ActionItemUpdate,
    AttendeeOut,
    CancelIn,
    ClientMeetings,
    CompleteIn,
    GuestIn,
    MeetingIn,
    MeetingOut,
    MeetingStats,
    MeetingUpdate,
    UserRef,
)
from app.modules.notifications.service import NotificationService
from app.platform.activity.service import ActivityRecorder
from app.platform.audit.service import AuditWriter
from app.platform.identity.models import User
from app.platform.notifications.interfaces import NotificationRequest

TYPE_LABELS = {
    "kickoff": "Kickoff",
    "review": "Review",
    "planning": "Planning",
    "internal": "Internal",
    "reporting": "Reporting",
    "other": "Meeting",
}
NOT_FOUND = "This meeting doesn't exist or you don't have access to it."


def _ref(user: User | None) -> UserRef | None:
    return UserRef(id=user.id, full_name=user.full_name) if user else None


class MeetingService:
    def __init__(self, session: AsyncSession, *, clock: Clock) -> None:
        self._repo = MeetingRepository(session)
        self._clock = clock
        self._audit = AuditWriter(session)
        self._activity = ActivityRecorder(session)
        self._notifier = NotificationService(session)

    # ------------------------------------------------------------ reads

    async def for_client(self, actor: Actor, client_id: uuid.UUID) -> ClientMeetings:
        client = await self._client(actor, client_id)
        meetings = await self._repo.for_client(client.id)
        can = await self._can_manage(actor, client)
        out = await self._many(meetings, client, can)
        return ClientMeetings(
            stats=MeetingStats(
                total=len(out),
                completed=sum(1 for m in out if m.status == "completed"),
                upcoming=sum(1 for m in out if m.status == "scheduled"),
                cancelled=sum(1 for m in out if m.status == "cancelled"),
            ),
            meetings=out,
            can_schedule=can,
        )

    async def get(self, actor: Actor, meeting_id: uuid.UUID) -> MeetingOut:
        meeting, client = await self._meeting(actor, meeting_id)
        return (await self._many([meeting], client, await self._can_manage(actor, client)))[0]

    # ------------------------------------------------------------ writes

    async def schedule(self, actor: Actor, data: MeetingIn) -> MeetingOut:
        client = await self._client(actor, data.client_id)
        await self._require_manage(actor, client)
        meeting = Meeting(
            client_id=client.id,
            title=data.title,
            description=data.description,
            type=data.type,
            starts_at=data.starts_at,
            ends_at=data.ends_at,
            platform=data.platform,
            location=data.location,
            agenda=data.agenda,
            created_by_id=actor.user_id,
        )
        self._repo.add(meeting)
        await self._repo.flush()
        internal = await self._set_attendees(meeting, data.attendee_ids, data.guests)
        await self._log(
            actor, client, meeting, "meeting.scheduled", f"{self._what(meeting)} scheduled"
        )
        await self._tell(actor, client, meeting, internal, f"Meeting scheduled: {meeting.title}")
        return await self.get(actor, meeting.id)

    async def update(self, actor: Actor, meeting_id: uuid.UUID, data: MeetingUpdate) -> MeetingOut:
        meeting, client = await self._open(actor, meeting_id)
        incoming = data.model_dump(exclude_unset=True, exclude={"attendee_ids", "guests"})
        if "title" in incoming and not incoming["title"]:
            raise ValidationFailed("The meeting needs a title.")
        for required in ("type", "starts_at", "ends_at"):
            if required in incoming and incoming[required] is None:
                raise ValidationFailed(f"The meeting's {required.replace('_', ' ')} is required.")
        starts = incoming.get("starts_at", meeting.starts_at)
        ends = incoming.get("ends_at", meeting.ends_at)
        if ends <= starts:
            raise ValidationFailed("The meeting must end after it starts.")
        moved = starts != meeting.starts_at
        changes: dict[str, Any] = {}
        for name, new in incoming.items():
            if getattr(meeting, name) != new:
                changes[name] = str(new) if new is not None else None
                setattr(meeting, name, new)
        internal: list[uuid.UUID] = []
        if data.attendee_ids is not None or data.guests is not None:
            current = (await self._repo.attendees([meeting.id]))[meeting.id]
            ids = (
                data.attendee_ids
                if data.attendee_ids is not None
                else [a.user_id for a, _ in current if a.user_id]
            )
            guests = (
                data.guests
                if data.guests is not None
                else [
                    GuestIn(name=a.name or "", email=a.email, organisation=a.organisation)
                    for a, _ in current
                    if a.user_id is None
                ]
            )
            internal = await self._set_attendees(meeting, ids, guests, replace=True)
            changes["attendees"] = len(internal) + len(guests)
        await self._repo.flush()
        if changes:
            await self._log(
                actor,
                client,
                meeting,
                "meeting.updated",
                f"{self._what(meeting)} updated",
                changes=changes,
            )
        if moved:
            ids = internal or [
                a.user_id
                for a, _ in (await self._repo.attendees([meeting.id]))[meeting.id]
                if a.user_id
            ]
            await self._tell(actor, client, meeting, ids, f"Meeting moved: {meeting.title}")
        return await self.get(actor, meeting.id)

    async def complete(self, actor: Actor, meeting_id: uuid.UUID, data: CompleteIn) -> MeetingOut:
        meeting, client = await self._open(actor, meeting_id)
        if meeting.starts_at > self._clock.now():
            raise BusinessRuleViolation("This meeting hasn't started yet.")
        meeting.status = "completed"
        meeting.notes = data.notes
        meeting.completed_at = self._clock.now()
        await self._repo.flush()
        await self._log(
            actor, client, meeting, "meeting.completed", f"{self._what(meeting)} completed"
        )
        return await self.get(actor, meeting.id)

    async def cancel(self, actor: Actor, meeting_id: uuid.UUID, data: CancelIn) -> MeetingOut:
        meeting, client = await self._open(actor, meeting_id)
        meeting.status = "cancelled"
        meeting.cancelled_reason = data.reason
        await self._repo.flush()
        await self._log(
            actor, client, meeting, "meeting.cancelled", f"{self._what(meeting)} cancelled"
        )
        ids = [
            a.user_id
            for a, _ in (await self._repo.attendees([meeting.id]))[meeting.id]
            if a.user_id
        ]
        await self._tell(actor, client, meeting, ids, f"Meeting cancelled: {meeting.title}")
        return await self.get(actor, meeting.id)

    async def add_action_item(
        self, actor: Actor, meeting_id: uuid.UUID, data: ActionItemIn
    ) -> MeetingOut:
        meeting, client = await self._managed(actor, meeting_id)
        await self._check_owner(data.owner_id)
        self._repo.add(
            MeetingActionItem(
                meeting_id=meeting.id,
                title=data.title,
                owner_id=data.owner_id,
                due_date=data.due_date,
            )
        )
        await self._repo.flush()
        if data.owner_id and data.owner_id != actor.user_id:
            await self._notifier.notify(
                NotificationRequest(
                    user_id=data.owner_id,
                    kind="meeting.action_item",
                    title=f"Action item for {client.name}: {data.title}",
                    link=f"/clients/{client.id}/meetings",
                    entity_type="meeting",
                    entity_id=str(meeting.id),
                )
            )
        return await self.get(actor, meeting.id)

    async def update_action_item(
        self, actor: Actor, item_id: uuid.UUID, data: ActionItemUpdate
    ) -> MeetingOut:
        item = await self._repo.action_item(item_id)
        if item is None:
            raise NotFound("This action item doesn't exist.")
        meeting, _ = await self._managed(actor, item.meeting_id, owner=item.owner_id)
        incoming = data.model_dump(exclude_unset=True)
        if "title" in incoming and not incoming["title"]:
            raise ValidationFailed("The action item needs a title.")
        if incoming.get("owner_id"):
            await self._check_owner(incoming["owner_id"])
        for name, new in incoming.items():
            setattr(item, name, new)
        if "done" in incoming:
            item.done_at = self._clock.now() if item.done else None
        await self._repo.flush()
        return await self.get(actor, meeting.id)

    async def delete_action_item(self, actor: Actor, item_id: uuid.UUID) -> MeetingOut:
        item = await self._repo.action_item(item_id)
        if item is None:
            raise NotFound("This action item doesn't exist.")
        meeting, _ = await self._managed(actor, item.meeting_id)
        await self._repo.delete(item)
        return await self.get(actor, meeting.id)

    # ------------------------------------------------------------ helpers

    async def _client(self, actor: Actor, client_id: uuid.UUID) -> Client:
        client = await self._repo.visible_client(actor, client_id)
        if client is None:
            raise NotFound("This client doesn't exist or you don't have access to it.")
        return client

    async def _meeting(self, actor: Actor, meeting_id: uuid.UUID) -> tuple[Meeting, Client]:
        meeting = await self._repo.meeting(meeting_id)
        client = await self._repo.visible_client(actor, meeting.client_id) if meeting else None
        if meeting is None or client is None:
            raise NotFound(NOT_FOUND)
        return meeting, client

    async def _managed(
        self, actor: Actor, meeting_id: uuid.UUID, *, owner: uuid.UUID | None = None
    ) -> tuple[Meeting, Client]:
        meeting, client = await self._meeting(actor, meeting_id)
        if owner != actor.user_id:  # an action item's owner may tick it off
            await self._require_manage(actor, client)
        return meeting, client

    async def _open(self, actor: Actor, meeting_id: uuid.UUID) -> tuple[Meeting, Client]:
        meeting, client = await self._managed(actor, meeting_id)
        if meeting.status != "scheduled":
            raise BusinessRuleViolation(f"This meeting is already {meeting.status}.")
        return meeting, client

    async def _can_manage(self, actor: Actor, client: Client) -> bool:
        return (
            actor.is_super_admin
            or client.account_manager_id == actor.user_id
            or actor.can(MEETINGS_MANAGE)
            or await self._repo.on_team(client.id, actor.user_id)
        )

    async def _require_manage(self, actor: Actor, client: Client) -> None:
        if not await self._can_manage(actor, client):
            raise Forbidden("Only the client's Account Manager and team can manage meetings.")

    async def _check_owner(self, owner_id: uuid.UUID | None) -> None:
        if owner_id and owner_id not in await self._repo.active_users([owner_id]):
            raise ValidationFailed("Choose an active team member as the owner.")

    async def _set_attendees(
        self,
        meeting: Meeting,
        user_ids: list[uuid.UUID],
        guests: list[GuestIn],
        *,
        replace: bool = False,
    ) -> list[uuid.UUID]:
        wanted = list(dict.fromkeys(user_ids))
        users = await self._repo.active_users(wanted)
        missing = [str(i) for i in wanted if i not in users]
        if missing:
            raise ValidationFailed(
                "Choose active team members as attendees.", details={"ids": missing}
            )
        rows = [MeetingAttendee(meeting_id=meeting.id, user_id=i) for i in wanted] + [
            MeetingAttendee(
                meeting_id=meeting.id,
                name=g.name,
                email=str(g.email) if g.email else None,
                organisation=g.organisation,
            )
            for g in guests
        ]
        if replace:
            await self._repo.replace_attendees(meeting.id, rows)
        else:
            for row in rows:
                self._repo.add(row)
            await self._repo.flush()
        return wanted

    def _display(self, meeting: Meeting) -> str:
        if meeting.status != "scheduled":
            return meeting.status
        return "upcoming" if meeting.ends_at > self._clock.now() else "awaiting_notes"

    async def _many(self, meetings: list[Meeting], client: Client, can: bool) -> list[MeetingOut]:
        ids = [m.id for m in meetings]
        attendees = await self._repo.attendees(ids)
        items = await self._repo.action_items(ids)
        return [
            MeetingOut(
                id=m.id,
                client_id=client.id,
                client_name=client.name,
                title=m.title,
                description=m.description,
                type=m.type,  # type: ignore[arg-type]  # DB check constraint
                status=m.status,  # type: ignore[arg-type]
                display_status=self._display(m),  # type: ignore[arg-type]
                starts_at=m.starts_at,
                ends_at=m.ends_at,
                platform=m.platform,  # type: ignore[arg-type]
                location=m.location,
                agenda=m.agenda,
                notes=m.notes,
                attendees=[
                    AttendeeOut(
                        id=a.id,
                        user=_ref(u),
                        name=u.full_name if u else (a.name or ""),
                        email=u.email if u else a.email,
                        organisation=a.organisation,
                        external=a.user_id is None,
                    )
                    for a, u in attendees[m.id]
                ],
                action_items=[
                    ActionItemOut(
                        id=i.id, title=i.title, owner=_ref(u), due_date=i.due_date, done=i.done
                    )
                    for i, u in items[m.id]
                ],
                completed_at=m.completed_at,
                cancelled_reason=m.cancelled_reason,
                can_manage=can,
            )
            for m in meetings
        ]

    @staticmethod
    def _what(meeting: Meeting) -> str:
        return f"{TYPE_LABELS[meeting.type]} meeting “{meeting.title}”"

    async def _tell(
        self,
        actor: Actor,
        client: Client,
        meeting: Meeting,
        user_ids: list[uuid.UUID],
        title: str,
    ) -> None:
        when = meeting.starts_at.strftime("%d %b %Y, %H:%M UTC")
        await self._notifier.notify_many(
            user_ids,
            NotificationRequest(
                user_id=actor.user_id,
                kind="meeting.invite",
                title=title,
                body=f"{client.name} · {when}",
                link=f"/clients/{client.id}/meetings",
                entity_type="meeting",
                entity_id=str(meeting.id),
            ),
            exclude=actor.user_id,
        )

    async def _log(
        self,
        actor: Actor,
        client: Client,
        meeting: Meeting,
        action: str,
        summary: str,
        *,
        changes: dict[str, Any] | None = None,
    ) -> None:
        await self._audit.record(
            action=action,
            entity_type="meeting",
            entity_id=meeting.id,
            actor_user_id=actor.user_id,
            changes=changes or {"title": meeting.title, "type": meeting.type},
            context={"client_id": str(client.id)},
        )
        await self._activity.record(
            verb=action.removeprefix("meeting."),
            subject_type="client",
            subject_id=client.id,
            actor_user_id=actor.user_id,
            summary=summary,
        )
