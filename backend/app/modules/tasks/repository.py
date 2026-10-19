"""Queries for the tasks module. A task is visible exactly when its project is."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import ColumnElement, Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.authz.actor import Actor
from app.authz.scopes import apply_scope
from app.modules.clients.models import Client
from app.modules.projects.models import Project
from app.modules.projects.repository import ProjectScope
from app.modules.tasks.models import CLOSED_STATUSES, Task
from app.platform.identity.models import User

Assignee = aliased(User)
Reviewer = aliased(User)

TaskRow = tuple[Task, Project, Client, User | None, User | None]


class TaskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _visible(self, actor: Actor, *filters: ColumnElement[bool]) -> Select[*tuple[Any, ...]]:
        stmt = (
            select(Task, Project, Client, Assignee, Reviewer)
            .join(Project, Project.id == Task.project_id)
            .join(Client, Client.id == Task.client_id)
            .outerjoin(Assignee, Assignee.id == Task.assignee_id)
            .outerjoin(Reviewer, Reviewer.id == Task.reviewer_id)
        )
        return apply_scope(stmt, actor, ProjectScope(), *filters)

    async def for_project(self, actor: Actor, project_id: uuid.UUID) -> list[TaskRow]:
        rows = await self._session.execute(
            self._visible(actor, Task.project_id == project_id).order_by(Task.number)
        )
        return [(t, p, c, a, r) for t, p, c, a, r in rows.all()]

    async def list_tasks(
        self, actor: Actor, *, assignee: uuid.UUID | None, open_only: bool, limit: int = 200
    ) -> list[TaskRow]:
        filters: list[ColumnElement[bool]] = []
        if assignee is not None:
            filters.append(Task.assignee_id == assignee)
        if open_only:
            filters.append(Task.status.not_in(CLOSED_STATUSES))
        rows = await self._session.execute(
            self._visible(actor, *filters)
            .order_by(Task.due_date.asc().nulls_last(), Task.number)
            .limit(limit)
        )
        return [(t, p, c, a, r) for t, p, c, a, r in rows.all()]

    async def get(self, actor: Actor, task_id: uuid.UUID, *, lock: bool = False) -> TaskRow | None:
        stmt = self._visible(actor, Task.id == task_id)
        if lock:
            stmt = stmt.with_for_update(of=Task)
        row = (await self._session.execute(stmt)).one_or_none()
        if row is None:
            return None
        task, project, client, assignee, reviewer = row
        return task, project, client, assignee, reviewer

    async def user(self, user_id: uuid.UUID) -> User | None:
        return await self._session.get(User, user_id)

    async def assignable_users(self) -> list[User]:
        rows = await self._session.execute(
            select(User)
            .where(User.is_active.is_(True), User.approved_at.is_not(None))
            .order_by(User.full_name)
        )
        return list(rows.scalars())

    def add(self, task: Task) -> None:
        self._session.add(task)

    async def flush(self) -> None:
        await self._session.flush()
