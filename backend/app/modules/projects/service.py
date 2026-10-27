"""Projects: list, view (with the task board) and create (clickable-demo rules).

Rules
- a project can only be created for a client whose onboarding is completed;
  creating the client's first project completes onboarding step 13;
- `projects.create` is required; the client must be visible to the actor;
- the manager must be an active Project Manager (or Super Admin);
- codes are PRJ-0001, PRJ-0002… from the transactional counter;
- the "SEO onboarding & foundation" template adds five tasks, dated from the
  start date, assigned to the first specialist on the client's team and
  reviewed by the project manager;
- progress = completed ÷ non-cancelled tasks;
- every create is audited and appears on the client's activity timeline.

TODO(pilot-port): confirm against services/projects.ts.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.actor import Actor
from app.authz.permissions import PROJECTS_CREATE, TASKS_CREATE
from app.core.clock import Clock
from app.core.errors import BusinessRuleViolation, Forbidden, NotFound, ValidationFailed
from app.modules.clients.models import Client
from app.modules.projects.models import Project
from app.modules.projects.repository import ProjectRepository
from app.modules.projects.schemas import (
    EligibleClient,
    ProjectCreate,
    ProjectDetail,
    ProjectListItem,
    ProjectStats,
)
from app.modules.projects.templates import TEMPLATES
from app.modules.tasks.models import Task
from app.modules.tasks.repository import TaskRepository
from app.modules.tasks.schemas import UserRef
from app.modules.tasks.service import task_item
from app.platform.activity.service import ActivityRecorder
from app.platform.audit.service import AuditWriter
from app.platform.identity.models import User
from app.platform.system.counters import format_code, next_value

ONBOARDING_REQUIRED = "Projects can only be created after client onboarding is completed."
NOT_FOUND = "This project doesn't exist or you don't have access to it."
EMPTY_STATS = (0, 0, 0, 0, 0)


@dataclass(frozen=True, slots=True)
class PlannedTask:
    """A task another module (services) asks a project to hold."""

    title: str
    due_date: date
    requires_review: bool
    requires_client_approval: bool
    assignee_id: uuid.UUID | None = None


def _ref(user: User) -> UserRef:
    return UserRef(id=user.id, full_name=user.full_name)


def _stats(raw: tuple[int, int, int, int, int]) -> ProjectStats:
    total, done, open_, overdue, in_review = raw
    return ProjectStats(
        tasks=total,
        open=open_,
        overdue=overdue,
        in_review=in_review,
        progress=round(done * 100 / total) if total else 0,
    )


class ProjectService:
    def __init__(self, session: AsyncSession, *, clock: Clock) -> None:
        self._session = session
        self._repo = ProjectRepository(session)
        self._tasks = TaskRepository(session)
        self._clock = clock
        self._audit = AuditWriter(session)
        self._activity = ActivityRecorder(session)

    # ------------------------------------------------------------ reads

    async def list_projects(
        self, actor: Actor, *, client_id: uuid.UUID | None = None
    ) -> list[ProjectListItem]:
        rows = await self._repo.list_projects(actor, client_id=client_id)
        stats = await self._repo.stats([p.id for p, _, _ in rows], self._today())
        return [
            ProjectListItem(
                id=project.id,
                code=project.code,
                name=project.name,
                client_id=client.id,
                client_name=client.name,
                manager=_ref(manager),
                start_date=project.start_date,
                stats=_stats(stats.get(project.id, EMPTY_STATS)),
            )
            for project, client, manager in rows
        ]

    async def get(self, actor: Actor, project_id: uuid.UUID) -> ProjectDetail:
        found = await self._repo.get(actor, project_id)
        if found is None:
            raise NotFound(NOT_FOUND)
        project, client, manager = found
        today = self._today()
        stats = await self._repo.stats([project.id], today)
        tasks = await self._tasks.for_project(actor, project.id)
        return ProjectDetail(
            id=project.id,
            code=project.code,
            name=project.name,
            client_id=client.id,
            client_name=client.name,
            manager=_ref(manager),
            start_date=project.start_date,
            stats=_stats(stats.get(project.id, EMPTY_STATS)),
            template=project.template,
            created_at=project.created_at,
            tasks=[task_item(row, today) for row in tasks],
            can_create_tasks=actor.can(TASKS_CREATE),
        )

    async def eligible_clients(self, actor: Actor) -> list[EligibleClient]:
        return [
            EligibleClient(id=c.id, code=c.code, name=c.name, has_project=has)
            for c, has in await self._repo.eligible_clients(actor)
        ]

    async def manager_options(self) -> list[UserRef]:
        return [_ref(u) for u in await self._repo.manager_options()]

    # ------------------------------------------------------------ writes

    async def create(self, actor: Actor, data: ProjectCreate) -> ProjectDetail:
        if not actor.can(PROJECTS_CREATE):
            raise Forbidden("You don't have permission to create projects.")
        client = await self._repo.client_visible(actor, data.client_id)
        if client is None:
            raise NotFound("This client doesn't exist or you don't have access to it.")
        if not await self._repo.onboarding_completed(client.id):
            raise BusinessRuleViolation(ONBOARDING_REQUIRED)
        manager = await self._repo.eligible_manager(data.manager_id)
        if manager is None:
            raise ValidationFailed(
                "Choose an active Project Manager.", details={"manager_id": str(data.manager_id)}
            )
        first_project = not await self._repo.clients_with_projects([client.id])

        project = Project(
            code=format_code("PRJ", await next_value(self._session, "project")),
            name=data.name,
            client_id=client.id,
            manager_id=manager.id,
            start_date=data.start_date,
            template=data.template if data.template != "blank" else None,
            created_by_id=actor.user_id,
        )
        await self._repo.add(project)
        created = await self._apply_template(project, client)

        await self._audit.record(
            action="project.created",
            entity_type="project",
            entity_id=project.id,
            actor_user_id=actor.user_id,
            changes={
                "name": project.name,
                "client_id": str(client.id),
                "manager_id": str(manager.id),
                "start_date": project.start_date.isoformat(),
                "template": project.template,
            },
            context={"code": project.code, "tasks_created": created},
        )
        summary = f"Project {project.code} created: {project.name}"
        if created:
            summary += f" ({created} tasks from template)"
        await self._activity.record(
            verb="project_created",
            subject_type="client",
            subject_id=client.id,
            actor_user_id=actor.user_id,
            summary=summary,
        )
        if first_project:
            await self._activity.record(
                verb="first_project_created",
                subject_type="client",
                subject_id=client.id,
                actor_user_id=actor.user_id,
                summary="Onboarding step 13 done: first project created",
            )
        return await self.get(actor, project.id)

    async def create_for_service(  # one argument per project field
        self,
        actor: Actor,
        *,
        client: Client,
        name: str,
        manager_id: uuid.UUID,
        start_date: date,
        tasks: list[PlannedTask],
        source: str,
    ) -> Project:
        """The delivery project of a client service (services module). The caller has
        checked `services.manage`; onboarding and the manager rules still apply here."""
        if not await self._repo.onboarding_completed(client.id):
            raise BusinessRuleViolation(ONBOARDING_REQUIRED)
        manager = await self._repo.eligible_manager(manager_id)
        if manager is None:
            raise ValidationFailed(
                "Choose an active Project Manager.", details={"manager_id": str(manager_id)}
            )
        first_project = not await self._repo.clients_with_projects([client.id])
        project = Project(
            code=format_code("PRJ", await next_value(self._session, "project")),
            name=name,
            client_id=client.id,
            manager_id=manager.id,
            start_date=start_date,
            template=None,
            created_by_id=actor.user_id,
        )
        await self._repo.add(project)
        await self.add_planned_tasks(project, tasks, created_by=actor.user_id)
        await self._audit.record(
            action="project.created",
            entity_type="project",
            entity_id=project.id,
            actor_user_id=actor.user_id,
            changes={
                "name": project.name,
                "client_id": str(client.id),
                "manager_id": str(manager.id),
                "start_date": project.start_date.isoformat(),
            },
            context={"code": project.code, "tasks_created": len(tasks), "source": source},
        )
        await self._activity.record(
            verb="project_created",
            subject_type="client",
            subject_id=client.id,
            actor_user_id=actor.user_id,
            summary=f"Project {project.code} created for {source}: {project.name}"
            + (f" ({len(tasks)} tasks from template)" if tasks else ""),
        )
        if first_project:
            await self._activity.record(
                verb="first_project_created",
                subject_type="client",
                subject_id=client.id,
                actor_user_id=actor.user_id,
                summary="Onboarding step 13 done: delivery started",
            )
        return project

    async def add_planned_tasks(
        self, project: Project, tasks: list[PlannedTask], *, created_by: uuid.UUID | None
    ) -> list[Task]:
        """Add tasks to a project, reviewed by its manager (services: monthly work)."""
        created = []
        for spec in tasks:
            task = Task(
                number=await next_value(self._session, "task"),
                project_id=project.id,
                client_id=project.client_id,
                title=spec.title,
                status="backlog",
                assignee_id=spec.assignee_id,
                reviewer_id=project.manager_id,
                requires_review=spec.requires_review,
                requires_client_approval=spec.requires_client_approval,
                due_date=spec.due_date,
                created_by_id=created_by,
            )
            self._tasks.add(task)
            created.append(task)
        await self._tasks.flush()
        return created

    async def project(self, project_id: uuid.UUID) -> Project | None:
        """Unscoped lookup for other modules that already checked access."""
        return await self._session.get(Project, project_id)

    async def manager_users(self) -> list[User]:
        return await self._repo.manager_options()

    # ------------------------------------------------------------ helpers

    async def _apply_template(self, project: Project, client: Client) -> int:
        template = TEMPLATES.get(project.template or "")
        if template is None:
            return 0
        assignee = await self._repo.first_team_employee(client.id)
        for spec in template.tasks:
            self._tasks.add(
                Task(
                    number=await next_value(self._session, "task"),
                    project_id=project.id,
                    client_id=client.id,
                    title=spec.title,
                    status="backlog",
                    assignee_id=assignee,
                    reviewer_id=project.manager_id,
                    requires_review=spec.requires_review,
                    requires_client_approval=spec.requires_client_approval,
                    due_date=project.start_date
                    + timedelta(days=spec.start_offset_days + spec.duration_days),
                    created_by_id=project.created_by_id,
                )
            )
        await self._tasks.flush()
        return len(template.tasks)

    def _today(self) -> date:
        return self._clock.now().date()
