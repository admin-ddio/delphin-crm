"""Queries for the onboarding module.

Visibility reuses the clients module's scope: you see a client's onboarding
exactly when you can see the client.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import Select, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.actor import Actor
from app.core.pagination import MAX_PAGE_SIZE, PageParams
from app.core.security import hash_token
from app.modules.clients.models import Client, ClientTeamMember
from app.modules.clients.repository import ClientRepository
from app.modules.onboarding.models import (
    ClientOnboarding,
    OnboardingAccessItem,
    OnboardingKpi,
    QuestionnaireLink,
)
from app.modules.onboarding.steps import DEFAULT_ACCESS_ITEMS
from app.modules.projects.models import Project
from app.platform.identity.models import Role, User, UserRole

#: Who can be on a client's internal team (demo: employees, team leads, project managers).
TEAM_ROLES = ("employee", "team_lead", "project_manager")


class OnboardingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._clients = ClientRepository(session)

    # ------------------------------------------------------------ clients (scoped)

    async def visible_client(
        self, actor: Actor, client_id: uuid.UUID
    ) -> tuple[Client, User] | None:
        return await self._clients.get(actor, client_id)

    async def visible_clients(self, actor: Actor) -> list[tuple[Client, User]]:
        """Up to MAX_PAGE_SIZE clients, alphabetical (enough for the interim board)."""
        params = PageParams(page=1, page_size=MAX_PAGE_SIZE)
        rows, _ = await self._clients.page(actor, params, search=None, status=None, sort=[])
        return rows

    async def client_for_update(self, client_id: uuid.UUID) -> Client:
        stmt = select(Client).where(Client.id == client_id).with_for_update()
        return (await self._session.execute(stmt)).scalar_one()

    # ------------------------------------------------------------ onboarding state

    async def state(self, client_id: uuid.UUID, *, lock: bool = False) -> ClientOnboarding:
        """The client's onboarding row, created with its access checklist on first use."""
        stmt = select(ClientOnboarding).where(ClientOnboarding.client_id == client_id)
        if lock:
            stmt = stmt.with_for_update()
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is not None:
            return row
        row = ClientOnboarding(client_id=client_id)
        self._session.add(row)
        for position, (key, label) in enumerate(DEFAULT_ACCESS_ITEMS):
            self._session.add(
                OnboardingAccessItem(client_id=client_id, key=key, label=label, position=position)
            )
        await self._session.flush()
        return row

    async def states(self, client_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, ClientOnboarding]:
        rows = await self._session.execute(
            select(ClientOnboarding).where(ClientOnboarding.client_id.in_(client_ids))
        )
        return {row.client_id: row for row in rows.scalars()}

    async def access_items(self, client_id: uuid.UUID) -> list[OnboardingAccessItem]:
        rows = await self._session.execute(
            select(OnboardingAccessItem)
            .where(OnboardingAccessItem.client_id == client_id)
            .order_by(OnboardingAccessItem.position)
        )
        return list(rows.scalars())

    async def access_items_for(
        self, client_ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, list[OnboardingAccessItem]]:
        rows = await self._session.execute(
            select(OnboardingAccessItem)
            .where(OnboardingAccessItem.client_id.in_(client_ids))
            .order_by(OnboardingAccessItem.position)
        )
        grouped: dict[uuid.UUID, list[OnboardingAccessItem]] = {}
        for item in rows.scalars():
            grouped.setdefault(item.client_id, []).append(item)
        return grouped

    async def access_item(self, client_id: uuid.UUID, key: str) -> OnboardingAccessItem | None:
        stmt = select(OnboardingAccessItem).where(
            OnboardingAccessItem.client_id == client_id, OnboardingAccessItem.key == key
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    # ------------------------------------------------------------ KPIs

    async def kpis(self, client_id: uuid.UUID) -> list[OnboardingKpi]:
        rows = await self._session.execute(
            select(OnboardingKpi)
            .where(OnboardingKpi.client_id == client_id)
            .order_by(OnboardingKpi.created_at, OnboardingKpi.id)
        )
        return list(rows.scalars())

    async def kpi_counts(self, client_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, tuple[int, int]]:
        """client_id → (total, unconfirmed)."""
        rows = await self._session.execute(
            select(
                OnboardingKpi.client_id,
                func.count(),
                func.count().filter(OnboardingKpi.confirmed_at.is_(None)),
            )
            .where(OnboardingKpi.client_id.in_(client_ids))
            .group_by(OnboardingKpi.client_id)
        )
        return {client_id: (int(total), int(open_)) for client_id, total, open_ in rows.all()}

    async def kpi(self, client_id: uuid.UUID, kpi_id: uuid.UUID) -> OnboardingKpi | None:
        stmt = select(OnboardingKpi).where(
            OnboardingKpi.client_id == client_id, OnboardingKpi.id == kpi_id
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    def add(self, obj: OnboardingKpi | QuestionnaireLink | ClientTeamMember) -> None:
        self._session.add(obj)

    async def delete_kpi(self, kpi: OnboardingKpi) -> None:
        await self._session.delete(kpi)

    async def flush(self) -> None:
        await self._session.flush()

    # ------------------------------------------------------------ team

    async def team(self, client_id: uuid.UUID) -> list[User]:
        rows = await self._session.execute(
            select(User)
            .join(ClientTeamMember, ClientTeamMember.user_id == User.id)
            .where(ClientTeamMember.client_id == client_id)
            .order_by(ClientTeamMember.added_at)
        )
        return list(rows.scalars())

    async def team_sizes(self, client_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, int]:
        rows = await self._session.execute(
            select(ClientTeamMember.client_id, func.count())
            .where(ClientTeamMember.client_id.in_(client_ids))
            .group_by(ClientTeamMember.client_id)
        )
        return {client_id: int(count) for client_id, count in rows.all()}

    async def clients_with_projects(self, client_ids: Sequence[uuid.UUID]) -> set[uuid.UUID]:
        """Step 13: which of these clients already have a project."""
        if not client_ids:
            return set()
        rows = await self._session.execute(
            select(Project.client_id).where(Project.client_id.in_(client_ids)).distinct()
        )
        return set(rows.scalars())

    def _team_candidates(self) -> Select[User]:
        return (
            select(User)
            .join(UserRole, UserRole.user_id == User.id)
            .join(Role, Role.id == UserRole.role_id)
            .where(
                Role.key.in_(TEAM_ROLES),
                User.is_active.is_(True),
                User.approved_at.is_not(None),
            )
            .distinct()
        )

    async def team_options(self) -> list[User]:
        rows = await self._session.execute(self._team_candidates().order_by(User.full_name))
        return list(rows.scalars())

    async def team_candidate(self, user_id: uuid.UUID) -> User | None:
        stmt = self._team_candidates().where(User.id == user_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def remove_team_member(self, client_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        result = await self._session.execute(
            delete(ClientTeamMember).where(
                ClientTeamMember.client_id == client_id, ClientTeamMember.user_id == user_id
            )
        )
        return bool(result.rowcount)  # type: ignore[attr-defined]

    async def users(self, ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, User]:
        if not ids:
            return {}
        rows = await self._session.execute(select(User).where(User.id.in_(ids)))
        return {user.id: user for user in rows.scalars()}

    # ------------------------------------------------------------ questionnaire links

    async def expire_links(self, client_id: uuid.UUID, now: datetime) -> None:
        await self._session.execute(
            update(QuestionnaireLink)
            .where(QuestionnaireLink.client_id == client_id, QuestionnaireLink.used_at.is_(None))
            .values(used_at=now)
        )

    async def usable_link(self, raw_token: str, now: datetime) -> QuestionnaireLink | None:
        stmt = (
            select(QuestionnaireLink)
            .where(
                QuestionnaireLink.token_hash == hash_token(raw_token),
                QuestionnaireLink.used_at.is_(None),
                QuestionnaireLink.expires_at > now,
            )
            .with_for_update()
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def client(self, client_id: uuid.UUID) -> Client:
        return (
            await self._session.execute(select(Client).where(Client.id == client_id))
        ).scalar_one()
