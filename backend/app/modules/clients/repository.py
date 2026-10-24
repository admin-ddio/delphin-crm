"""Queries for the clients module. Every client read goes through ClientScope."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import ColumnElement, Select, func, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.authz.actor import Actor
from app.authz.permissions import CLIENTS_VIEW_ALL, SUPER_ADMIN
from app.authz.scopes import apply_scope
from app.core.pagination import PageParams
from app.modules.clients.models import Client, ClientTeamMember
from app.modules.onboarding.models import ClientOnboarding
from app.platform.activity.models import ActivityEvent
from app.platform.identity.models import Role, User, UserRole

# Roles offered as a client's Account Manager (demo: Account Managers and Super Admins).
ACCOUNT_MANAGER_ROLES = ("account_manager", SUPER_ADMIN)

SORTS: dict[str, InstrumentedAttribute[Any]] = {
    "name": Client.name,
    "code": Client.code,
    "created_at": Client.created_at,
}


class ClientScope:
    """Who sees which clients.

    Demo rule: Super Admin, Account Managers, Project Managers and Finance see every
    client (`clients.view_all`); everyone else only clients they work on: as the
    client's Account Manager or on its internal team (onboarding step 10).
    TODO(pilot-port): also clients where the actor has assigned tasks, once tasks exist.
    """

    def clause(self, actor: Actor) -> ColumnElement[bool]:
        if actor.can(CLIENTS_VIEW_ALL):
            return true()
        on_team = select(ClientTeamMember.client_id).where(
            ClientTeamMember.user_id == actor.user_id
        )
        return or_(Client.account_manager_id == actor.user_id, Client.id.in_(on_team))


class ClientRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._scope = ClientScope()

    # ------------------------------------------------------------ reads (scoped)

    def _visible(self, actor: Actor, *filters: ColumnElement[bool]) -> Select[Client, User]:
        stmt = select(Client, User).join(User, User.id == Client.account_manager_id)
        return apply_scope(stmt, actor, self._scope, *filters)

    async def page(
        self,
        actor: Actor,
        params: PageParams,
        *,
        search: str | None,
        status: str | None,
        sort: Sequence[tuple[str, str]],
    ) -> tuple[list[tuple[Client, User]], int]:
        filters: list[ColumnElement[bool]] = []
        if search:
            pattern = f"%{search.strip()}%"
            filters.append(
                or_(
                    Client.name.ilike(pattern),
                    Client.code.ilike(pattern),
                    Client.domain.ilike(pattern),
                )
            )
        if status:
            filters.append(Client.status == status)
        stmt = self._visible(actor, *filters)
        total = (
            await self._session.execute(select(func.count()).select_from(stmt.subquery()))
        ).scalar_one()
        order = [
            SORTS[field].desc() if direction == "desc" else SORTS[field].asc()
            for field, direction in sort
        ] or [Client.name.asc()]
        rows = await self._session.execute(
            stmt.order_by(*order, Client.id).offset(params.offset).limit(params.limit)
        )
        return [(client, manager) for client, manager in rows.all()], int(total)

    async def get(self, actor: Actor, client_id: uuid.UUID) -> tuple[Client, User] | None:
        result = await self._session.execute(self._visible(actor, Client.id == client_id))
        row = result.one_or_none()
        if row is None:
            return None
        client, manager = row
        return client, manager

    # ------------------------------------------------------------ duplicate checks (unscoped)

    async def by_domain(self, domain: str, *, exclude: uuid.UUID | None = None) -> Client | None:
        stmt = select(Client).where(Client.domain == domain)
        if exclude is not None:
            stmt = stmt.where(Client.id != exclude)
        return (await self._session.execute(stmt.limit(1))).scalar_one_or_none()

    async def by_normalized_name(
        self, normalized: str, *, exclude: uuid.UUID | None = None
    ) -> Client | None:
        if not normalized:
            return None
        stmt = select(Client).where(Client.normalized_name == normalized)
        if exclude is not None:
            stmt = stmt.where(Client.id != exclude)
        return (await self._session.execute(stmt.limit(1))).scalar_one_or_none()

    # ------------------------------------------------------------ people

    def _account_managers(self) -> Select[User]:
        return (
            select(User)
            .join(UserRole, UserRole.user_id == User.id)
            .join(Role, Role.id == UserRole.role_id)
            .where(
                Role.key.in_(ACCOUNT_MANAGER_ROLES),
                User.is_active.is_(True),
                User.approved_at.is_not(None),
            )
            .distinct()
        )

    async def account_manager_options(self) -> list[User]:
        rows = await self._session.execute(self._account_managers().order_by(User.full_name))
        return list(rows.scalars())

    async def eligible_account_manager(self, user_id: uuid.UUID) -> User | None:
        stmt = self._account_managers().where(User.id == user_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def user(self, user_id: uuid.UUID) -> User | None:
        return await self._session.get(User, user_id)

    # ------------------------------------------------------------ writes

    async def add(self, client: Client) -> None:
        self._session.add(client)
        await self._session.flush()

    async def flush(self) -> None:
        await self._session.flush()

    # ------------------------------------------------------------ activity

    async def activity(
        self, client_id: uuid.UUID, limit: int = 100
    ) -> list[tuple[ActivityEvent, User | None]]:
        rows = await self._session.execute(
            select(ActivityEvent, User)
            .outerjoin(User, User.id == ActivityEvent.actor_user_id)
            .where(
                ActivityEvent.subject_type == "client",
                ActivityEvent.subject_id == str(client_id),
            )
            .order_by(ActivityEvent.occurred_at.desc())
            .limit(limit)
        )
        return [(event, user) for event, user in rows.all()]

    async def last_activity(self, client_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, datetime]:
        """Latest timeline event per client (list "Last activity" column)."""
        if not client_ids:
            return {}
        rows = await self._session.execute(
            select(ActivityEvent.subject_id, func.max(ActivityEvent.occurred_at))
            .where(
                ActivityEvent.subject_type == "client",
                ActivityEvent.subject_id.in_([str(i) for i in client_ids]),
            )
            .group_by(ActivityEvent.subject_id)
        )
        return {uuid.UUID(subject): at for subject, at in rows.all()}

    async def status_counts(self, actor: Actor) -> dict[str, int]:
        """Visible clients per status (list tabs)."""
        stmt = apply_scope(
            select(Client.status, func.count()).group_by(Client.status), actor, self._scope
        )
        rows = await self._session.execute(stmt)
        return {status: int(count) for status, count in rows.all()}

    async def onboarded(self, client_id: uuid.UUID) -> bool:
        stmt = select(ClientOnboarding.completed_at).where(ClientOnboarding.client_id == client_id)
        return (await self._session.execute(stmt)).scalar_one_or_none() is not None
