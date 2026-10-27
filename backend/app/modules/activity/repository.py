"""Queries for the activity log: client timeline events the actor may see."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ColumnElement, Select, String, and_, cast, false, or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.actor import Actor
from app.modules.clients.models import Client
from app.modules.clients.repository import ClientScope
from app.platform.activity.models import ActivityEvent
from app.platform.identity.models import User

Row = tuple[ActivityEvent, Client, User | None]

#: area → (exact verbs, verb prefixes). Unlisted verbs are "other".
AREAS: dict[str, tuple[frozenset[str], tuple[str, ...]]] = {
    "clients": (frozenset({"created", "updated", "status_changed"}), ("contract_",)),
    "onboarding": (
        frozenset({"reviewed", "completed", "reopened"}),
        ("questionnaire_", "access_", "kpi", "kickoff_", "team_", "onboarding_", "review_"),
    ),
    "projects": (frozenset({"project_created", "first_project_created"}), ("task_", "project_")),
    "approvals": (
        frozenset({"submitted", "approved", "changes_requested"}),
        ("approval_", "client_decision"),
    ),
    "documents": (frozenset({"uploaded"}), ("document_", "folder_")),
    "meetings": (frozenset({"scheduled"}), ("meeting_",)),
    "services": (frozenset({"services_added"}), ("service_",)),
}


def area_of(verb: str) -> str:
    for area, (exact, prefixes) in AREAS.items():
        if verb in exact or verb.startswith(prefixes):
            return area
    return "other"


def _area_clause(area: str) -> ColumnElement[bool]:
    if area == "other":
        return ~or_(*(_area_clause(a) for a in AREAS))
    exact, prefixes = AREAS.get(area, (frozenset(), ()))
    conditions = [ActivityEvent.verb.in_(exact)] if exact else []
    conditions += [ActivityEvent.verb.like(f"{p}%") for p in prefixes]
    return or_(*conditions) if conditions else false()


class ActivityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._scope = ClientScope()

    def _visible(self, actor: Actor) -> Select[*tuple[Any, ...]]:
        return (
            select(ActivityEvent, Client, User)
            .join(
                Client,
                and_(
                    ActivityEvent.subject_type == "client",
                    ActivityEvent.subject_id == cast(Client.id, String),
                ),
            )
            .outerjoin(User, User.id == ActivityEvent.actor_user_id)
            .where(self._scope.clause(actor))
        )

    async def page(
        self,
        actor: Actor,
        *,
        limit: int,
        client_id: uuid.UUID | None = None,
        actor_id: uuid.UUID | None = None,
        area: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        before: tuple[datetime, uuid.UUID] | None = None,
    ) -> list[Row]:
        stmt = self._visible(actor)
        if client_id:
            stmt = stmt.where(Client.id == client_id)
        if actor_id:
            stmt = stmt.where(ActivityEvent.actor_user_id == actor_id)
        if area:
            stmt = stmt.where(_area_clause(area))
        if since:
            stmt = stmt.where(ActivityEvent.occurred_at >= since)
        if until:
            stmt = stmt.where(ActivityEvent.occurred_at < until)
        if before:
            stmt = stmt.where(tuple_(ActivityEvent.occurred_at, ActivityEvent.id) < before)
        stmt = stmt.order_by(ActivityEvent.occurred_at.desc(), ActivityEvent.id.desc()).limit(limit)
        return [
            (event, client, user)
            for event, client, user in (await self._session.execute(stmt)).all()
        ]

    async def people(self, actor: Actor) -> list[User]:
        visible = self._visible(actor).with_only_columns(ActivityEvent.actor_user_id).distinct()
        stmt = select(User).where(User.id.in_(visible.scalar_subquery())).order_by(User.full_name)
        return list((await self._session.execute(stmt)).scalars())
