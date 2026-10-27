"""Queries for services and retainers. Client services are scoped through ClientScope."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.actor import Actor
from app.authz.permissions import SERVICES_VIEW_ALL
from app.modules.clients.models import Client, ClientTeamMember
from app.modules.clients.repository import ClientScope
from app.modules.onboarding.models import ClientOnboarding
from app.modules.projects.models import Project
from app.modules.services.models import (
    OPEN_STATUSES,
    ServiceEngagement,
    ServiceOccurrence,
    ServiceTemplateTask,
    ServiceType,
)
from app.modules.tasks.models import Task
from app.modules.team.models import Department, Employee
from app.platform.identity.models import User

ServiceRow = tuple[ServiceEngagement, ServiceType, Client, User | None, Project | None]


class ServiceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._clients = ClientScope()

    # ------------------------------------------------------------ catalogue

    async def types(self) -> list[ServiceType]:
        rows = await self._session.execute(select(ServiceType).order_by(ServiceType.sort))
        return list(rows.scalars())

    async def type_by_key(self, key: str) -> ServiceType | None:
        stmt = select(ServiceType).where(ServiceType.key == key)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def template(
        self, service_type_id: uuid.UUID, phase: str | None = None
    ) -> list[ServiceTemplateTask]:
        stmt = select(ServiceTemplateTask).where(
            ServiceTemplateTask.service_type_id == service_type_id,
            ServiceTemplateTask.is_active.is_(True),
        )
        if phase is not None:
            stmt = stmt.where(ServiceTemplateTask.phase == phase)
        stmt = stmt.order_by(ServiceTemplateTask.phase, ServiceTemplateTask.sort)
        return list((await self._session.execute(stmt)).scalars())

    async def template_rows(self, service_type_id: uuid.UUID) -> list[ServiceTemplateTask]:
        """Active and retired rows (for updates)."""
        stmt = select(ServiceTemplateTask).where(
            ServiceTemplateTask.service_type_id == service_type_id
        )
        return list((await self._session.execute(stmt)).scalars())

    # ------------------------------------------------------------ client services

    def _visible(self, actor: Actor) -> Select[*tuple[Any, ...]]:
        stmt: Select[*tuple[Any, ...]] = (
            select(ServiceEngagement, ServiceType, Client, User, Project)
            .join(ServiceType, ServiceType.id == ServiceEngagement.service_type_id)
            .join(Client, Client.id == ServiceEngagement.client_id)
            .outerjoin(User, User.id == ServiceEngagement.manager_id)
            .outerjoin(Project, Project.id == ServiceEngagement.project_id)
        )
        if actor.can(SERVICES_VIEW_ALL):
            return stmt
        # Otherwise: services of clients the actor works on, or services they manage.
        return stmt.where(
            (self._clients.clause(actor)) | (ServiceEngagement.manager_id == actor.user_id)
        )

    async def rows(
        self,
        actor: Actor,
        *,
        kind: str | None = None,
        status: str | None = None,
        client_id: uuid.UUID | None = None,
    ) -> list[ServiceRow]:
        stmt = self._visible(actor)
        if kind:
            stmt = stmt.where(ServiceEngagement.kind == kind)
        if status:
            stmt = stmt.where(ServiceEngagement.status == status)
        if client_id:
            stmt = stmt.where(ServiceEngagement.client_id == client_id)
        stmt = stmt.order_by(Client.name, ServiceType.sort, ServiceEngagement.created_at)
        return [tuple(row) for row in (await self._session.execute(stmt)).all()]

    async def get(self, actor: Actor, service_id: uuid.UUID) -> ServiceRow | None:
        stmt = self._visible(actor).where(ServiceEngagement.id == service_id)
        row = (await self._session.execute(stmt)).one_or_none()
        return tuple(row) if row else None

    async def lock(self, service_id: uuid.UUID) -> ServiceEngagement | None:
        stmt = select(ServiceEngagement).where(ServiceEngagement.id == service_id).with_for_update()
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def for_client(self, client_id: uuid.UUID) -> list[tuple[ServiceEngagement, ServiceType]]:
        stmt = (
            select(ServiceEngagement, ServiceType)
            .join(ServiceType, ServiceType.id == ServiceEngagement.service_type_id)
            .where(ServiceEngagement.client_id == client_id)
            .order_by(ServiceType.sort, ServiceEngagement.created_at)
        )
        return [(cs, st) for cs, st in (await self._session.execute(stmt)).all()]

    async def open_retainer(self, client_id: uuid.UUID, service_type_id: uuid.UUID) -> bool:
        stmt = select(ServiceEngagement.id).where(
            ServiceEngagement.client_id == client_id,
            ServiceEngagement.service_type_id == service_type_id,
            ServiceEngagement.kind == "retainer",
            ServiceEngagement.status.in_(OPEN_STATUSES),
        )
        return (await self._session.execute(stmt)).first() is not None

    async def active_retainers(self) -> list[ServiceEngagement]:
        stmt = select(ServiceEngagement).where(
            ServiceEngagement.kind == "retainer",
            ServiceEngagement.status == "active",
            ServiceEngagement.project_id.is_not(None),
        )
        return list((await self._session.execute(stmt)).scalars())

    async def onboarding_completed(self, client_id: uuid.UUID) -> bool:
        stmt = select(ClientOnboarding.completed_at).where(ClientOnboarding.client_id == client_id)
        return (await self._session.execute(stmt)).scalar_one_or_none() is not None

    async def client(self, client_id: uuid.UUID) -> Client | None:
        return await self._session.get(Client, client_id)

    async def team_member(self, client_id: uuid.UUID, area: str | None) -> uuid.UUID | None:
        """The client team member covering the area, else the first one with no area."""
        if area is None:
            return None
        stmt = (
            select(ClientTeamMember.user_id)
            .join(User, User.id == ClientTeamMember.user_id)
            .where(
                ClientTeamMember.client_id == client_id,
                ClientTeamMember.area == area,
                User.is_active.is_(True),
            )
            .order_by(ClientTeamMember.added_at)
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    # ------------------------------------------------------------ occurrences and progress

    async def occurrences(self, service_id: uuid.UUID) -> list[ServiceOccurrence]:
        stmt = select(ServiceOccurrence).where(ServiceOccurrence.client_service_id == service_id)
        return list((await self._session.execute(stmt)).scalars())

    async def occurrence_keys(self, service_id: uuid.UUID, period: str) -> set[uuid.UUID]:
        stmt = select(ServiceOccurrence.template_task_id).where(
            ServiceOccurrence.client_service_id == service_id,
            ServiceOccurrence.occurrence_key == period,
        )
        return set((await self._session.execute(stmt)).scalars())

    async def month_progress(
        self, service_ids: Sequence[uuid.UUID]
    ) -> dict[tuple[uuid.UUID, str], tuple[int, int]]:
        """(service, YYYY-MM) → (non-cancelled tasks, completed tasks)."""
        if not service_ids:
            return {}
        stmt = (
            select(
                ServiceOccurrence.client_service_id,
                ServiceOccurrence.occurrence_key,
                func.count(Task.id).filter(Task.status != "cancelled"),
                func.count(Task.id).filter(Task.status == "completed"),
            )
            .join(Task, Task.id == ServiceOccurrence.task_id)
            .where(ServiceOccurrence.client_service_id.in_(service_ids))
            .group_by(ServiceOccurrence.client_service_id, ServiceOccurrence.occurrence_key)
        )
        return {
            (sid, key): (int(total), int(done))
            for sid, key, total, done in (await self._session.execute(stmt)).all()
        }

    async def project_progress(
        self, project_ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, tuple[int, int]]:
        if not project_ids:
            return {}
        stmt = (
            select(
                Task.project_id,
                func.count(Task.id).filter(Task.status != "cancelled"),
                func.count(Task.id).filter(Task.status == "completed"),
            )
            .where(Task.project_id.in_(project_ids))
            .group_by(Task.project_id)
        )
        return {
            pid: (int(total), int(done))
            for pid, total, done in (await self._session.execute(stmt)).all()
        }

    async def delivery_manager_user(self, department_id: uuid.UUID | None) -> uuid.UUID | None:
        """Sign-in account of the department's default Project Manager (org structure)."""
        if department_id is None:
            return None
        stmt = (
            select(Employee.user_id)
            .join(Department, Department.delivery_manager_id == Employee.id)
            .where(Department.id == department_id, Employee.status != "exited")
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    def add(self, obj: ServiceEngagement | ServiceOccurrence | ServiceTemplateTask) -> None:
        self._session.add(obj)

    async def flush(self) -> None:
        await self._session.flush()

    async def visible_client(self, actor: Actor, client_id: uuid.UUID) -> Client | None:
        stmt = select(Client).where(Client.id == client_id, self._clients.clause(actor))
        return (await self._session.execute(stmt)).scalar_one_or_none()
