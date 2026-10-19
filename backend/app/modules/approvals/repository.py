"""Queries for the approvals module. An approval is visible exactly when its task's project is."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any, Literal

from sqlalchemy import ColumnElement, Select, and_, case, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.authz.actor import Actor
from app.authz.scopes import apply_scope
from app.modules.approvals.models import Approval, TaskVersion
from app.modules.clients.models import Client
from app.modules.projects.models import Project
from app.modules.projects.repository import ProjectScope
from app.modules.tasks.models import Task
from app.platform.identity.models import User

Approver = aliased(User)
Requester = aliased(User)
ClientManager = aliased(User)

ApprovalRow = tuple[Approval, TaskVersion, Task, Client, User | None, User | None, User]


class ApprovalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------ per task

    async def versions(self, task_id: uuid.UUID) -> list[TaskVersion]:
        rows = await self._session.execute(
            select(TaskVersion).where(TaskVersion.task_id == task_id).order_by(TaskVersion.number)
        )
        return list(rows.scalars())

    async def approvals(self, task_id: uuid.UUID) -> list[Approval]:
        rows = await self._session.execute(
            select(Approval).where(Approval.task_id == task_id).order_by(Approval.created_at)
        )
        return list(rows.scalars())

    async def open_for_task(self, task_id: uuid.UUID, *, lock: bool = False) -> Approval | None:
        stmt = select(Approval).where(Approval.task_id == task_id, Approval.status == "submitted")
        if lock:
            stmt = stmt.with_for_update()
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def next_version_number(self, task_id: uuid.UUID) -> int:
        stmt = select(func.coalesce(func.max(TaskVersion.number), 0)).where(
            TaskVersion.task_id == task_id
        )
        return int((await self._session.execute(stmt)).scalar_one()) + 1

    async def cancel_open(self, task_id: uuid.UUID) -> int:
        result = await self._session.execute(
            update(Approval)
            .where(Approval.task_id == task_id, Approval.status == "submitted")
            .values(status="cancelled")
            .execution_options(synchronize_session="fetch")
        )
        return int(result.rowcount)  # type: ignore[attr-defined]

    async def users(self, ids: Sequence[uuid.UUID | None]) -> dict[uuid.UUID, User]:
        wanted = {i for i in ids if i is not None}
        if not wanted:
            return {}
        rows = await self._session.execute(select(User).where(User.id.in_(wanted)))
        return {user.id: user for user in rows.scalars()}

    async def client_manager(self, client_id: uuid.UUID) -> User | None:
        stmt = (
            select(User)
            .join(Client, Client.account_manager_id == User.id)
            .where(Client.id == client_id)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    def add(self, obj: TaskVersion | Approval) -> None:
        self._session.add(obj)

    async def flush(self) -> None:
        await self._session.flush()

    # ------------------------------------------------------------ lists

    def _visible(self, actor: Actor, *filters: ColumnElement[bool]) -> Select[*tuple[Any, ...]]:
        stmt = (
            select(Approval, TaskVersion, Task, Client, Approver, Requester, ClientManager)
            .join(TaskVersion, TaskVersion.id == Approval.version_id)
            .join(Task, Task.id == Approval.task_id)
            .join(Project, Project.id == Task.project_id)
            .join(Client, Client.id == Approval.client_id)
            .join(ClientManager, ClientManager.id == Client.account_manager_id)
            .outerjoin(Approver, Approver.id == Approval.approver_id)
            .outerjoin(Requester, Requester.id == Approval.requested_by_id)
        )
        return apply_scope(stmt, actor, ProjectScope(), *filters)

    async def list_approvals(
        self, actor: Actor, *, view: Literal["mine", "all"], limit: int = 200
    ) -> list[ApprovalRow]:
        filters: list[ColumnElement[bool]] = []
        if view == "mine":
            filters.append(Approval.status == "submitted")
            filters.append(
                or_(
                    and_(Approval.stage == "internal", Approval.approver_id == actor.user_id),
                    and_(Approval.stage == "client", Client.account_manager_id == actor.user_id),
                )
            )
        rows = await self._session.execute(
            self._visible(actor, *filters)
            .order_by(
                Approval.created_at.desc(),
                TaskVersion.number.desc(),
                case((Approval.stage == "client", 0), else_=1),
            )
            .limit(limit)
        )
        return [(a, v, t, c, ap, rq, am) for a, v, t, c, ap, rq, am in rows.all()]

    async def get(self, actor: Actor, approval_id: uuid.UUID) -> ApprovalRow | None:
        row = (
            await self._session.execute(self._visible(actor, Approval.id == approval_id))
        ).one_or_none()
        if row is None:
            return None
        a, v, t, c, ap, rq, am = row
        return a, v, t, c, ap, rq, am
