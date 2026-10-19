"""Queries for the onboarding module.

Client visibility always goes through ClientRepository (ClientScope). The onboarding
row and its access checklist are created lazily on first use, so clients created
before onboarding existed still work.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import Select, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.actor import Actor
from app.core.pagination import MAX_PAGE_SIZE, PageParams
from app.core.security import hash_token
from app.modules.clients.models import Client, ClientTeamMember
from app.modules.clients.repository import ClientRepository
from app.modules.documents.models import Document, DocumentFolder
from app.modules.meetings.models import Meeting
from app.modules.onboarding.models import (
    ClientOnboarding,
    OnboardingAccessItem,
    OnboardingKpi,
    QuestionnaireLink,
)
from app.modules.onboarding.steps import DEFAULT_ACCESS_ITEMS
from app.modules.projects.models import Project
from app.platform.identity.models import Role, User, UserRole

#: Who can be assigned to a client's internal team (demo).
TEAM_ROLES = ("employee", "team_lead", "project_manager", "account_manager", "super_admin")
KICKOFF_TYPES = ("kickoff", "internal")


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
        """Up to MAX_PAGE_SIZE clients, alphabetical (enough for the board)."""
        params = PageParams(page=1, page_size=MAX_PAGE_SIZE)
        rows, _ = await self._clients.page(actor, params, search=None, status=None, sort=[])
        return rows

    async def client(self, client_id: uuid.UUID) -> Client:
        return (
            await self._session.execute(select(Client).where(Client.id == client_id))
        ).scalar_one()

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
        for position, (key, label, description) in enumerate(DEFAULT_ACCESS_ITEMS):
            self._session.add(
                OnboardingAccessItem(
                    client_id=client_id,
                    key=key,
                    label=label,
                    description=description,
                    position=position,
                )
            )
        await self._session.flush()
        return row

    async def states(self, client_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, ClientOnboarding]:
        rows = await self._session.execute(
            select(ClientOnboarding).where(ClientOnboarding.client_id.in_(client_ids))
        )
        return {row.client_id: row for row in rows.scalars()}

    # ------------------------------------------------------------ access checklist

    async def access_items(self, client_id: uuid.UUID) -> list[OnboardingAccessItem]:
        rows = await self._session.execute(
            select(OnboardingAccessItem)
            .where(OnboardingAccessItem.client_id == client_id)
            .order_by(OnboardingAccessItem.position, OnboardingAccessItem.label)
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
        grouped: dict[uuid.UUID, list[OnboardingAccessItem]] = defaultdict(list)
        for item in rows.scalars():
            grouped[item.client_id].append(item)
        return grouped

    async def delete_access_item(self, item: OnboardingAccessItem) -> None:
        await self._session.delete(item)
        await self._session.flush()

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

    async def delete_kpi(self, kpi: OnboardingKpi) -> None:
        await self._session.delete(kpi)
        await self._session.flush()

    # ------------------------------------------------------------ meetings (kickoffs)

    async def kickoff_meetings(
        self, client_ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, list[Meeting]]:
        """Non-cancelled kickoff and internal meetings, oldest first."""
        out: dict[uuid.UUID, list[Meeting]] = defaultdict(list)
        if not client_ids:
            return out
        rows = await self._session.execute(
            select(Meeting)
            .where(
                Meeting.client_id.in_(client_ids),
                Meeting.type.in_(KICKOFF_TYPES),
                Meeting.status != "cancelled",
            )
            .order_by(Meeting.starts_at)
        )
        for meeting in rows.scalars():
            out[meeting.client_id].append(meeting)
        return out

    # ------------------------------------------------------------ documents

    async def document_counts(self, client_id: uuid.UUID) -> tuple[int, int]:
        """(all documents, documents in the Contracts folder)."""
        stmt = (
            select(func.count(), func.count().filter(DocumentFolder.name == "Contracts"))
            .select_from(Document)
            .join(DocumentFolder, DocumentFolder.id == Document.folder_id)
            .where(Document.client_id == client_id)
        )
        total, contracts = (await self._session.execute(stmt)).one()
        return int(total), int(contracts)

    # ------------------------------------------------------------ team

    async def team(self, client_id: uuid.UUID) -> list[tuple[ClientTeamMember, User]]:
        rows = await self._session.execute(
            select(ClientTeamMember, User)
            .join(User, User.id == ClientTeamMember.user_id)
            .where(ClientTeamMember.client_id == client_id)
            .order_by(ClientTeamMember.added_at, User.full_name)
        )
        return [(member, user) for member, user in rows.all()]

    async def team_sizes(self, client_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, int]:
        rows = await self._session.execute(
            select(ClientTeamMember.client_id, func.count())
            .where(ClientTeamMember.client_id.in_(client_ids))
            .group_by(ClientTeamMember.client_id)
        )
        return {client_id: int(count) for client_id, count in rows.all()}

    async def role_names(self, user_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, str]:
        """Each user's first role name (team table 'Role' column)."""
        if not user_ids:
            return {}
        rows = await self._session.execute(
            select(UserRole.user_id, Role.name)
            .join(Role, Role.id == UserRole.role_id)
            .where(UserRole.user_id.in_(user_ids))
            .order_by(UserRole.assigned_at)
        )
        out: dict[uuid.UUID, str] = {}
        for user_id, name in rows.all():
            out.setdefault(user_id, name)
        return out

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

    async def users(self, ids: Sequence[uuid.UUID | None]) -> dict[uuid.UUID, User]:
        wanted = {i for i in ids if i}
        if not wanted:
            return {}
        rows = await self._session.execute(select(User).where(User.id.in_(wanted)))
        return {user.id: user for user in rows.scalars()}

    # ------------------------------------------------------------ projects (step 13)

    async def clients_with_projects(self, client_ids: Sequence[uuid.UUID]) -> set[uuid.UUID]:
        if not client_ids:
            return set()
        rows = await self._session.execute(
            select(Project.client_id).where(Project.client_id.in_(client_ids)).distinct()
        )
        return set(rows.scalars())

    # ------------------------------------------------------------ questionnaire links

    async def expire_links(self, client_id: uuid.UUID, now: datetime) -> None:
        await self._session.execute(
            update(QuestionnaireLink)
            .where(QuestionnaireLink.client_id == client_id, QuestionnaireLink.used_at.is_(None))
            .values(used_at=now)
        )

    async def usable_link(
        self, raw_token: str, now: datetime, *, lock: bool = False
    ) -> QuestionnaireLink | None:
        stmt = select(QuestionnaireLink).where(
            QuestionnaireLink.token_hash == hash_token(raw_token),
            QuestionnaireLink.used_at.is_(None),
            QuestionnaireLink.expires_at > now,
        )
        if lock:
            stmt = stmt.with_for_update()
        return (await self._session.execute(stmt)).scalar_one_or_none()

    # ------------------------------------------------------------ writes

    def add(
        self,
        obj: OnboardingKpi | QuestionnaireLink | ClientTeamMember | OnboardingAccessItem,
    ) -> None:
        self._session.add(obj)

    async def flush(self) -> None:
        await self._session.flush()

    async def onboarding_clients(self) -> list[tuple[Client, User]]:
        """Every client still in onboarding (unscoped: for system jobs only)."""
        rows = await self._session.execute(
            select(Client, User)
            .join(User, User.id == Client.account_manager_id)
            .where(Client.status == "onboarding")
            .order_by(Client.created_at)
        )
        return [(client, manager) for client, manager in rows.all()]
