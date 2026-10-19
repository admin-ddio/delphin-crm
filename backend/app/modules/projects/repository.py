"""Queries for the projects module. Every project read goes through ProjectScope."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import date

from sqlalchemy import ColumnElement, Select, func, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.actor import Actor
from app.authz.permissions import PROJECTS_VIEW_ALL, SUPER_ADMIN
from app.authz.scopes import apply_scope
from app.modules.clients.models import Client, ClientTeamMember
from app.modules.clients.repository import ClientScope
from app.modules.onboarding.models import ClientOnboarding
from app.modules.projects.models import Project
from app.modules.tasks.models import CLOSED_STATUSES, Task
from app.platform.identity.models import Role, User, UserRole

#: Roles offered as a project's manager.
MANAGER_ROLES = ("project_manager", SUPER_ADMIN)
REVIEW_STATUSES = ("internal_review", "client_approval")


class ProjectScope:
    """Demo rule: AM, PM, Finance and Super Admin see every project
    (`projects.view_all`); others only projects they work on: as its manager,
    on the client's team, or with a task assigned to them."""

    def clause(self, actor: Actor) -> ColumnElement[bool]:
        if actor.can(PROJECTS_VIEW_ALL):
            return true()
        on_team = select(ClientTeamMember.client_id).where(
            ClientTeamMember.user_id == actor.user_id
        )
        with_task = select(Task.project_id).where(Task.assignee_id == actor.user_id)
        return or_(
            Project.manager_id == actor.user_id,
            Project.client_id.in_(on_team),
            Project.id.in_(with_task),
        )


class ProjectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._scope = ProjectScope()

    def _visible(
        self, actor: Actor, *filters: ColumnElement[bool]
    ) -> Select[Project, Client, User]:
        stmt = (
            select(Project, Client, User)
            .join(Client, Client.id == Project.client_id)
            .join(User, User.id == Project.manager_id)
        )
        return apply_scope(stmt, actor, self._scope, *filters)

    async def list_projects(
        self, actor: Actor, *, client_id: uuid.UUID | None = None
    ) -> list[tuple[Project, Client, User]]:
        filters = [Project.client_id == client_id] if client_id else []
        rows = await self._session.execute(
            self._visible(actor, *filters).order_by(Project.created_at.desc(), Project.code.desc())
        )
        return [(project, client, manager) for project, client, manager in rows.all()]

    async def get(self, actor: Actor, project_id: uuid.UUID) -> tuple[Project, Client, User] | None:
        row = (
            await self._session.execute(self._visible(actor, Project.id == project_id))
        ).one_or_none()
        if row is None:
            return None
        project, client, manager = row
        return project, client, manager

    async def stats(
        self, project_ids: Sequence[uuid.UUID], today: date
    ) -> dict[uuid.UUID, tuple[int, int, int, int, int]]:
        """project → (non-cancelled, completed, open, overdue, in review)."""
        if not project_ids:
            return {}
        open_ = Task.status.not_in(CLOSED_STATUSES)
        rows = await self._session.execute(
            select(
                Task.project_id,
                func.count().filter(Task.status != "cancelled"),
                func.count().filter(Task.status == "completed"),
                func.count().filter(open_),
                func.count().filter(open_, Task.due_date < today),
                func.count().filter(Task.status.in_(REVIEW_STATUSES)),
            )
            .where(Task.project_id.in_(project_ids))
            .group_by(Task.project_id)
        )
        return {
            pid: (int(total), int(done), int(open_n), int(late), int(review))
            for pid, total, done, open_n, late, review in rows.all()
        }

    # ------------------------------------------------------------ creation helpers

    async def eligible_clients(self, actor: Actor) -> list[tuple[Client, bool]]:
        """Clients the actor can see whose onboarding is completed, with 'has a project'."""
        has_project = select(Project.id).where(Project.client_id == Client.id).exists()
        stmt = apply_scope(
            select(Client, has_project)
            .join(ClientOnboarding, ClientOnboarding.client_id == Client.id)
            .where(ClientOnboarding.completed_at.is_not(None)),
            actor,
            ClientScope(),
        ).order_by(Client.name)
        rows = await self._session.execute(stmt)
        return [(client, bool(flag)) for client, flag in rows.all()]

    async def client_visible(self, actor: Actor, client_id: uuid.UUID) -> Client | None:
        stmt = apply_scope(select(Client).where(Client.id == client_id), actor, ClientScope())
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def onboarding_completed(self, client_id: uuid.UUID) -> bool:
        stmt = select(ClientOnboarding.completed_at).where(ClientOnboarding.client_id == client_id)
        return (await self._session.execute(stmt)).scalar_one_or_none() is not None

    def _managers(self) -> Select[User]:
        return (
            select(User)
            .join(UserRole, UserRole.user_id == User.id)
            .join(Role, Role.id == UserRole.role_id)
            .where(
                Role.key.in_(MANAGER_ROLES), User.is_active.is_(True), User.approved_at.is_not(None)
            )
            .distinct()
        )

    async def manager_options(self) -> list[User]:
        return list(
            (await self._session.execute(self._managers().order_by(User.full_name))).scalars()
        )

    async def eligible_manager(self, user_id: uuid.UUID) -> User | None:
        stmt = self._managers().where(User.id == user_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def first_team_employee(self, client_id: uuid.UUID) -> uuid.UUID | None:
        """Template tasks go to the first specialist on the client's team (demo)."""
        stmt = (
            select(User.id)
            .join(ClientTeamMember, ClientTeamMember.user_id == User.id)
            .join(UserRole, UserRole.user_id == User.id)
            .join(Role, Role.id == UserRole.role_id)
            .where(ClientTeamMember.client_id == client_id, Role.key == "employee")
            .order_by(ClientTeamMember.added_at)
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def add(self, project: Project) -> None:
        self._session.add(project)
        await self._session.flush()

    async def clients_with_projects(self, client_ids: Sequence[uuid.UUID]) -> set[uuid.UUID]:
        if not client_ids:
            return set()
        rows = await self._session.execute(
            select(Project.client_id).where(Project.client_id.in_(client_ids)).distinct()
        )
        return set(rows.scalars())
