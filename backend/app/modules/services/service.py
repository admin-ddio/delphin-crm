"""Services and retainers (services plan, 2026-10-27; demo rules for retainers).

Rules
- services are chosen at client creation (at least one) and may be added later;
  a client has at most one open (planned / active / paused) SEO and one Social
  Media retainer; project services (Website, Web App, Mobile App) may repeat;
- `services.manage` adds, starts, pauses, resumes, completes and cancels services,
  for clients the actor is the Account Manager of (Super Admin: any client);
- a service starts only after client onboarding is completed; starting creates the
  delivery project (setup tasks for retainers, delivery phases for projects, dated
  from the start date) and completes onboarding step 13 for the first service;
- the default Project Manager is the delivering department's delivery manager;
- retainers generate their monthly tasks from the month after they start, into
  their project; generation is idempotent per (service, template task, YYYY-MM),
  due dates move off weekends; only active retainers generate;
- tasks go to the client team member covering the template task's area, and are
  reviewed by the project's manager;
- fees are visible to `finance.view` (Account Managers, Finance) only;
- everyone sees services of clients they can see; `services.view_all` sees all;
- template edits need `services.templates.manage`; retired template tasks are kept
  (is_active false) so history stays linked;
- every change is audited and appears on the client's activity timeline.
TODO(pilot-port): confirm against services/retainers.ts.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.actor import Actor
from app.authz.permissions import (
    FINANCE_VIEW,
    JOBS_RUN,
    SERVICES_MANAGE,
    SERVICES_TEMPLATES_MANAGE,
)
from app.core.clock import Clock, business_today
from app.core.errors import BusinessRuleViolation, Conflict, Forbidden, NotFound, ValidationFailed
from app.modules.clients.models import Client
from app.modules.notifications.service import NotificationService
from app.modules.onboarding.service import add_access_items
from app.modules.projects.service import PlannedTask, ProjectService
from app.modules.services.catalogue import access_items_for
from app.modules.services.models import (
    ServiceEngagement,
    ServiceOccurrence,
    ServiceTemplateTask,
    ServiceType,
)
from app.modules.services.repository import ServiceRepository, ServiceRow
from app.modules.services.scheduling import monthly_due, period_key, phase_due
from app.modules.services.schemas import (
    ClientRef,
    GenerateResult,
    MonthSummary,
    Progress,
    ProjectRef,
    Ref,
    ServiceDetail,
    ServiceItem,
    ServicePermissions,
    ServiceSelection,
    ServicesOverview,
    ServicesTiles,
    ServiceTemplates,
    ServiceTypeOut,
    StartOptions,
    StartService,
    TemplateTaskOut,
    TemplateUpdate,
)
from app.modules.tasks.repository import TaskRepository
from app.modules.tasks.schemas import UserRef
from app.modules.tasks.service import task_item
from app.platform.activity.service import ActivityRecorder
from app.platform.audit.service import AuditWriter
from app.platform.notifications.interfaces import NotificationRequest
from app.platform.system.counters import format_code, next_value

STATUS_LABELS = {
    "planned": "Planned",
    "active": "Active",
    "paused": "Paused",
    "completed": "Completed",
    "cancelled": "Cancelled",
}
NOT_FOUND = "This service doesn't exist or you don't have access to it."
ONBOARDING_FIRST = "Services can only start after client onboarding is completed."
#: Lifecycle: action → (allowed from, to, verb for the timeline).
TRANSITIONS: dict[str, tuple[tuple[str, ...], str, str]] = {
    "pause": (("active",), "paused", "paused"),
    "resume": (("paused",), "active", "resumed"),
    "complete": (("active", "paused"), "completed", "completed"),
    "cancel": (("planned", "active", "paused"), "cancelled", "cancelled"),
}


def _type_out(t: ServiceType, departments: dict[uuid.UUID, str] | None = None) -> ServiceTypeOut:
    name = (departments or {}).get(t.department_id) if t.department_id else None
    return ServiceTypeOut(
        id=t.id,
        key=t.key,
        name=t.name,
        kind=t.kind,  # type: ignore[arg-type]  # DB check constraint
        department=Ref(id=t.department_id, name=name) if t.department_id and name else None,
        is_active=t.is_active,
    )


def _month_start(day: date) -> date:
    return day.replace(day=1)


class ServicesService:
    def __init__(self, session: AsyncSession, *, clock: Clock) -> None:
        self._session = session
        self._repo = ServiceRepository(session)
        self._projects = ProjectService(session, clock=clock)
        self._tasks = TaskRepository(session)
        self._clock = clock
        self._audit = AuditWriter(session)
        self._activity = ActivityRecorder(session)
        self._notifier = NotificationService(session)

    # ================================================================ catalogue and templates

    async def types(self) -> list[ServiceTypeOut]:
        return [_type_out(t) for t in await self._repo.types()]

    async def templates(self, actor: Actor, key: str) -> ServiceTemplates:
        service_type = await self._type(key)
        return ServiceTemplates(
            service=_type_out(service_type),
            tasks=[self._template_out(t) for t in await self._repo.template(service_type.id)],
            can_edit=actor.can(SERVICES_TEMPLATES_MANAGE),
        )

    async def update_templates(
        self, actor: Actor, key: str, data: TemplateUpdate
    ) -> ServiceTemplates:
        if not actor.can(SERVICES_TEMPLATES_MANAGE):
            raise Forbidden("You can't edit service templates.")
        service_type = await self._type(key)
        allowed = {"monthly", "setup"} if service_type.kind == "retainer" else {"delivery"}
        rows = {r.id: r for r in await self._repo.template_rows(service_type.id)}
        kept: set[uuid.UUID] = set()
        sort: dict[str, int] = defaultdict(int)
        added = changed = 0
        for item in data.tasks:
            if item.phase not in allowed:
                phases = " and ".join(sorted(allowed))
                raise ValidationFailed(f"{service_type.name} templates have {phases} tasks only.")
            if (item.phase == "monthly") != (item.day_of_month is not None):
                raise ValidationFailed(
                    f"{item.title}: monthly tasks need a day of the month (1–28); others don't."
                )
            values = {
                "phase": item.phase,
                "title": item.title,
                "day_of_month": item.day_of_month,
                "start_offset_days": item.start_offset_days,
                "duration_days": item.duration_days,
                "requires_review": item.requires_review,
                "requires_client_approval": item.requires_client_approval,
                "area": item.area,
                "sort": sort[item.phase],
                "is_active": True,
            }
            sort[item.phase] += 1
            if item.id is not None:
                row = rows.get(item.id)
                if row is None:
                    raise ValidationFailed("That template task doesn't belong to this service.")
                if any(getattr(row, k) != v for k, v in values.items()):
                    changed += 1
                for k, v in values.items():
                    setattr(row, k, v)
                kept.add(row.id)
            else:
                self._repo.add(ServiceTemplateTask(service_type_id=service_type.id, **values))
                added += 1
        retired = 0
        for row in rows.values():
            if row.id not in kept and row.is_active:
                row.is_active = False
                retired += 1
        await self._repo.flush()
        if added or changed or retired:
            await self._audit.record(
                action="service_template.updated",
                entity_type="service_type",
                entity_id=service_type.id,
                actor_user_id=actor.user_id,
                changes={"added": added, "changed": changed, "retired": retired},
                context={"key": service_type.key},
            )
        return await self.templates(actor, key)

    # ================================================================ client services

    async def add_for_client(
        self,
        actor: Actor,
        client: Client,
        selections: list[ServiceSelection],
        *,
        at_creation: bool = False,
    ) -> list[ServiceEngagement]:
        """Add services to a client (called by the clients module at creation too)."""
        if not at_creation:
            self._require_manage(actor, client)
        if not selections:
            raise ValidationFailed("Choose at least one service.")
        types = {t.key: t for t in await self._repo.types()}
        seen: set[str] = set()
        created: list[ServiceEngagement] = []
        for selection in selections:
            service_type = types.get(selection.service_key)
            if service_type is None or not service_type.is_active:
                raise ValidationFailed(
                    f"Unknown service '{selection.service_key}'.",
                    details={"service_key": selection.service_key},
                )
            if service_type.kind == "retainer" and (
                selection.service_key in seen
                or await self._repo.open_retainer(client.id, service_type.id)
            ):
                raise Conflict(
                    f"{client.name} already has a {service_type.name} retainer. "
                    "A client can have one at a time."
                )
            seen.add(selection.service_key)
            engagement = ServiceEngagement(
                code=format_code("SRV", await next_value(self._session, "service")),
                client_id=client.id,
                service_type_id=service_type.id,
                kind=service_type.kind,
                status="planned",
                fee=selection.fee,
                notes=selection.notes,
                created_by_id=actor.user_id,
            )
            self._repo.add(engagement)
            created.append(engagement)
        await self._repo.flush()
        names = ", ".join(types[s.service_key].name for s in selections)
        for engagement in created:
            await self._audit.record(
                action="service.added",
                entity_type="client_service",
                entity_id=engagement.id,
                actor_user_id=actor.user_id,
                changes={
                    "service_type_id": str(engagement.service_type_id),
                    "fee": _money(engagement.fee),
                },
                context={"code": engagement.code, "client_id": str(client.id)},
            )
        await self._activity.record(
            verb="services_added",
            subject_type="client",
            subject_id=client.id,
            actor_user_id=actor.user_id,
            summary=f"Services {'chosen' if at_creation else 'added'}: {names}",
        )
        if not at_creation:
            # Onboarding still open: extend its access checklist for the new services.
            await add_access_items(self._session, client.id, access_items_for(list(seen)))
        return created

    async def add_services(
        self, actor: Actor, client_id: uuid.UUID, selections: list[ServiceSelection]
    ) -> list[ServiceItem]:
        client = await self._repo.visible_client(actor, client_id)
        if client is None:
            raise NotFound("This client doesn't exist or you don't have access to it.")
        await self.add_for_client(actor, client, selections)
        return await self.for_client(actor, client.id)

    async def overview(
        self,
        actor: Actor,
        *,
        kind: str | None = None,
        status: str | None = None,
        client_id: uuid.UUID | None = None,
    ) -> ServicesOverview:
        rows = await self._repo.rows(actor, kind=kind, status=status, client_id=client_id)
        everything = (
            rows if not (kind or status) else await self._repo.rows(actor, client_id=client_id)
        )
        items = await self._items(actor, rows)
        money = actor.can(FINANCE_VIEW)
        retainers = [
            r[0] for r in everything if r[0].kind == "retainer" and r[0].status == "active"
        ]
        return ServicesOverview(
            tiles=ServicesTiles(
                active_retainers=len(retainers),
                projects_in_progress=sum(
                    1 for r in everything if r[0].kind == "project" and r[0].status == "active"
                ),
                planned=sum(1 for r in everything if r[0].status == "planned"),
                contracted_monthly=sum((r.fee or Decimal(0) for r in retainers), Decimal(0))
                if money
                else None,
            ),
            items=items,
        )

    async def for_client(self, actor: Actor, client_id: uuid.UUID) -> list[ServiceItem]:
        return await self._items(actor, await self._repo.rows(actor, client_id=client_id))

    async def get(self, actor: Actor, service_id: uuid.UUID) -> ServiceDetail:
        row = await self._row(actor, service_id)
        engagement, _, client, _, project = row
        (item,) = await self._items(actor, [row])
        today = self._today()
        current = period_key(today) if engagement.kind == "retainer" else None
        tasks = []
        history: list[MonthSummary] = []
        if project is not None:
            task_rows = await self._tasks.for_project(actor, project.id)
            if engagement.kind == "retainer":
                occurrences = await self._repo.occurrences(engagement.id)
                this_month = {o.task_id for o in occurrences if o.occurrence_key == current}
                task_rows = [r for r in task_rows if r[0].id in this_month]
                progress = await self._repo.month_progress([engagement.id])
                history = [
                    MonthSummary(period=key, total=total, done=done)
                    for (_, key), (total, done) in sorted(
                        progress.items(), key=lambda kv: kv[0][1], reverse=True
                    )
                ]
            tasks = [task_item(r, today) for r in task_rows]
        return ServiceDetail(
            **item.model_dump(),
            notes=engagement.notes,
            created_at=engagement.created_at,
            onboarding_completed=await self._repo.onboarding_completed(client.id),
            current_period=current,
            tasks=tasks,
            history=history,
            permissions=ServicePermissions(
                manage=self._can_manage(actor, client),
                generate=engagement.kind == "retainer"
                and engagement.status == "active"
                and (
                    actor.can_any(JOBS_RUN, SERVICES_MANAGE)
                    or engagement.manager_id == actor.user_id
                ),
                see_money=actor.can(FINANCE_VIEW),
            ),
        )

    async def start_options(self, actor: Actor, service_id: uuid.UUID) -> StartOptions:
        _, service_type, client, _, _ = await self._row(actor, service_id)
        managers = [
            UserRef(id=u.id, full_name=u.full_name) for u in await self._projects.manager_users()
        ]
        default_id = await self._repo.delivery_manager_user(service_type.department_id)
        default = next((m for m in managers if m.id == default_id), None)
        return StartOptions(
            default_manager=default,
            managers=managers,
            onboarding_completed=await self._repo.onboarding_completed(client.id),
        )

    async def start(self, actor: Actor, service_id: uuid.UUID, data: StartService) -> ServiceDetail:
        engagement, service_type, client, _, _ = await self._row(actor, service_id)
        self._require_manage(actor, client)
        engagement = await self._lock(engagement.id)
        if engagement.status != "planned":
            raise BusinessRuleViolation(
                f"This service is {engagement.status}; only planned services start."
            )
        if not await self._repo.onboarding_completed(client.id):
            raise BusinessRuleViolation(ONBOARDING_FIRST)
        phase = "setup" if engagement.kind == "retainer" else "delivery"
        planned = [
            PlannedTask(
                title=t.title,
                due_date=phase_due(data.start_date, t.start_offset_days, t.duration_days),
                requires_review=t.requires_review,
                requires_client_approval=t.requires_client_approval,
                assignee_id=await self._repo.team_member(client.id, t.area),
            )
            for t in await self._repo.template(service_type.id, phase)
        ]
        project = await self._projects.create_for_service(
            actor,
            client=client,
            name=f"{client.name}: {service_type.name}",
            manager_id=data.manager_id,
            start_date=data.start_date,
            tasks=planned,
            source=f"{engagement.code} {service_type.name}",
        )
        engagement.project_id = project.id
        engagement.manager_id = data.manager_id
        engagement.start_date = data.start_date
        engagement.status = "active"
        await self._repo.flush()
        await self._audit.record(
            action="service.started",
            entity_type="client_service",
            entity_id=engagement.id,
            actor_user_id=actor.user_id,
            changes={
                "status": ["planned", "active"],
                "project_id": str(project.id),
                "manager_id": str(data.manager_id),
                "start_date": data.start_date.isoformat(),
            },
            context={"code": engagement.code},
        )
        await self._activity.record(
            verb="service_started",
            subject_type="client",
            subject_id=client.id,
            actor_user_id=actor.user_id,
            summary=f"{service_type.name} started ({engagement.code}, project {project.code})",
        )
        if data.manager_id != actor.user_id:
            await self._notifier.notify(
                NotificationRequest(
                    user_id=data.manager_id,
                    kind="service.started",
                    title=f"You're the Project Manager for {client.name}: {service_type.name}",
                    body=f"{len(planned)} tasks are on the project board.",
                    link=f"/services/{engagement.id}",
                    entity_type="client_service",
                    entity_id=str(engagement.id),
                )
            )
        return await self.get(actor, engagement.id)

    async def transition(self, actor: Actor, service_id: uuid.UUID, action: str) -> ServiceDetail:
        engagement, service_type, client, _, _ = await self._row(actor, service_id)
        self._require_manage(actor, client)
        allowed, target, verb = TRANSITIONS[action]
        engagement = await self._lock(engagement.id)
        if engagement.status not in allowed:
            raise BusinessRuleViolation(
                f"A {STATUS_LABELS[engagement.status].lower()} service can't be {verb}."
            )
        old = engagement.status
        engagement.status = target
        if target in ("completed", "cancelled"):
            engagement.end_date = max(self._today(), engagement.start_date or self._today())
        await self._repo.flush()
        await self._audit.record(
            action=f"service.{verb}",
            entity_type="client_service",
            entity_id=engagement.id,
            actor_user_id=actor.user_id,
            changes={"status": [old, target]},
            context={"code": engagement.code},
        )
        await self._activity.record(
            verb=f"service_{verb}",
            subject_type="client",
            subject_id=client.id,
            actor_user_id=actor.user_id,
            summary=f"{service_type.name} {verb} ({engagement.code})",
        )
        return await self.get(actor, engagement.id)

    # ================================================================ monthly generation

    async def generate(self, actor: Actor, service_id: uuid.UUID) -> GenerateResult:
        engagement, _, _, _, _ = await self._row(actor, service_id)
        if not (actor.can_any(JOBS_RUN, SERVICES_MANAGE) or engagement.manager_id == actor.user_id):
            raise Forbidden("You can't generate this retainer's tasks.")
        if engagement.kind != "retainer":
            raise BusinessRuleViolation("Only retainers have monthly tasks.")
        if engagement.status != "active":
            raise BusinessRuleViolation("Only active retainers generate monthly tasks.")
        return await self._generate(engagement.id, self._today(), actor_id=actor.user_id)

    async def generate_all(self) -> dict[str, int]:
        """The monthly job: every active retainer, current month (idempotent)."""
        today = self._today()
        created = skipped = services = 0
        for engagement in await self._repo.active_retainers():
            result = await self._generate(engagement.id, today, actor_id=None)
            services += 1
            created += result.created
            skipped += result.skipped
        return {"retainers": services, "created": created, "skipped": skipped}

    async def _generate(
        self, service_id: uuid.UUID, today: date, *, actor_id: uuid.UUID | None
    ) -> GenerateResult:
        engagement = await self._lock(service_id)
        period = _month_start(today)
        key = period_key(period)
        start = engagement.start_date
        # Monthly work starts the month after the retainer starts (setup covers month 1).
        if (
            engagement.status != "active"
            or engagement.project_id is None
            or start is None
            or period <= _month_start(start)
        ):
            return GenerateResult(period=key, created=0, skipped=0)
        project = await self._projects.project(engagement.project_id)
        if project is None:
            return GenerateResult(period=key, created=0, skipped=0)
        template = await self._repo.template(engagement.service_type_id, "monthly")
        done = await self._repo.occurrence_keys(engagement.id, key)
        todo = [t for t in template if t.id not in done]
        planned = [
            PlannedTask(
                title=f"{t.title} ({period:%b %Y})",
                due_date=monthly_due(period, t.day_of_month or 1),
                requires_review=t.requires_review,
                requires_client_approval=t.requires_client_approval,
                assignee_id=await self._repo.team_member(engagement.client_id, t.area),
            )
            for t in todo
        ]
        tasks = await self._projects.add_planned_tasks(project, planned, created_by=actor_id)
        for template_task, task in zip(todo, tasks, strict=True):
            self._repo.add(
                ServiceOccurrence(
                    client_service_id=engagement.id,
                    template_task_id=template_task.id,
                    occurrence_key=key,
                    task_id=task.id,
                )
            )
        await self._repo.flush()
        if tasks:
            await self._activity.record(
                verb="service_month_generated",
                subject_type="client",
                subject_id=engagement.client_id,
                actor_user_id=actor_id,
                summary=(
                    f"{len(tasks)} monthly tasks created for {period:%B %Y} ({engagement.code})"
                ),
            )
            if engagement.manager_id:
                await self._notifier.notify(
                    NotificationRequest(
                        user_id=engagement.manager_id,
                        kind="service.month_generated",
                        title=f"{period:%B} tasks are ready ({engagement.code})",
                        body=f"{len(tasks)} monthly tasks were added to {project.name}.",
                        link=f"/services/{engagement.id}",
                        entity_type="client_service",
                        entity_id=str(engagement.id),
                    )
                )
        return GenerateResult(period=key, created=len(tasks), skipped=len(template) - len(todo))

    # ================================================================ helpers

    def _today(self) -> date:
        return business_today(self._clock)

    async def _type(self, key: str) -> ServiceType:
        service_type = await self._repo.type_by_key(key)
        if service_type is None:
            raise NotFound("This service type doesn't exist.")
        return service_type

    async def _row(self, actor: Actor, service_id: uuid.UUID) -> ServiceRow:
        row = await self._repo.get(actor, service_id)
        if row is None:
            raise NotFound(NOT_FOUND)
        return row

    async def _lock(self, service_id: uuid.UUID) -> ServiceEngagement:
        engagement = await self._repo.lock(service_id)
        if engagement is None:
            raise NotFound(NOT_FOUND)
        return engagement

    @staticmethod
    def _can_manage(actor: Actor, client: Client) -> bool:
        return actor.can(SERVICES_MANAGE) and (
            actor.is_super_admin or client.account_manager_id == actor.user_id
        )

    def _require_manage(self, actor: Actor, client: Client) -> None:
        if not self._can_manage(actor, client):
            raise Forbidden("Only the client's Account Manager can change its services.")

    @staticmethod
    def _template_out(t: ServiceTemplateTask) -> TemplateTaskOut:
        return TemplateTaskOut(
            id=t.id,
            phase=t.phase,  # type: ignore[arg-type]
            title=t.title,
            day_of_month=t.day_of_month,
            start_offset_days=t.start_offset_days,
            duration_days=t.duration_days,
            requires_review=t.requires_review,
            requires_client_approval=t.requires_client_approval,
            area=t.area,  # type: ignore[arg-type]
            sort=t.sort,
        )

    async def _items(self, actor: Actor, rows: list[ServiceRow]) -> list[ServiceItem]:
        money = actor.can(FINANCE_VIEW)
        key = period_key(self._today())
        months = await self._repo.month_progress([r[0].id for r in rows if r[0].kind == "retainer"])
        projects = await self._repo.project_progress(
            [r[0].project_id for r in rows if r[0].kind == "project" and r[0].project_id]
        )
        items = []
        for engagement, service_type, client, manager, project in rows:
            if engagement.kind == "retainer":
                total, done = months.get((engagement.id, key), (0, 0))
            else:
                total, done = (
                    projects.get(engagement.project_id, (0, 0)) if engagement.project_id else (0, 0)
                )
            items.append(
                ServiceItem(
                    id=engagement.id,
                    code=engagement.code,
                    client=ClientRef(id=client.id, code=client.code, name=client.name),
                    service=_type_out(service_type),
                    status=engagement.status,  # type: ignore[arg-type]
                    status_label=STATUS_LABELS[engagement.status],
                    fee=engagement.fee if money else None,
                    currency=engagement.currency,
                    start_date=engagement.start_date,
                    end_date=engagement.end_date,
                    manager=UserRef(id=manager.id, full_name=manager.full_name)
                    if manager
                    else None,
                    project=ProjectRef(id=project.id, code=project.code, name=project.name)
                    if project
                    else None,
                    progress=Progress(total=total, done=done),
                )
            )
        return items


def _money(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None
