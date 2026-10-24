"""Tasks: create, assign, schedule and move through the board (clickable-demo rules).

Who may do what
- create a task: `tasks.create` on a project the actor can see;
- work a task (start, block, finish, send back to ready): its assignee, or a
  task manager;
- task managers (edit, reassign, cancel, reopen): Super Admin, the project's
  manager, or a Team Lead.

Rules
- moves follow TRANSITIONS; review/approval states are entered only through the
  approvals module (submit / decide), so from there a task can only be cancelled
  (which cancels the open request);
- a task that requires review or client approval can't be completed directly;
- completed tasks are final; cancelled tasks can be reopened to the backlog;
- every change is audited and appears on the client's activity timeline.

TODO(pilot-port): confirm against services/tasks.ts.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any, Final, Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.actor import Actor
from app.authz.permissions import TASKS_CREATE
from app.core.clock import Clock
from app.core.errors import BusinessRuleViolation, Forbidden, NotFound, ValidationFailed
from app.modules.approvals.models import Approval, TaskVersion
from app.modules.approvals.repository import ApprovalRepository
from app.modules.approvals.rules import CHANNEL_LABELS, OpenRequest, decision_block
from app.modules.clients.models import Client
from app.modules.projects.models import Project
from app.modules.projects.repository import ProjectRepository
from app.modules.tasks.models import CLOSED_STATUSES, TASK_STATUSES, Task
from app.modules.tasks.repository import TaskRepository, TaskRow
from app.modules.tasks.schemas import (
    FeedbackOut,
    OpenApproval,
    StatusChange,
    TaskCreate,
    TaskDetail,
    TaskItem,
    TaskPermissions,
    TaskStatus,
    TaskUpdate,
    UserRef,
    VersionOut,
)
from app.platform.activity.service import ActivityRecorder
from app.platform.audit.service import AuditWriter
from app.platform.identity.models import User
from app.platform.system.counters import next_value

STATUS_LABELS: Final[dict[str, str]] = {
    "backlog": "Backlog",
    "ready": "Ready",
    "in_progress": "In progress",
    "blocked": "Blocked",
    "internal_review": "Internal review",
    "client_approval": "Client approval",
    "completed": "Completed",
    "cancelled": "Cancelled",
}
#: Board moves: current status → statuses it may move to.
TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    "backlog": frozenset({"ready", "in_progress", "cancelled"}),
    "ready": frozenset({"backlog", "in_progress", "cancelled"}),
    "in_progress": frozenset({"blocked", "completed", "ready", "cancelled"}),
    "blocked": frozenset({"in_progress", "cancelled"}),
    "internal_review": frozenset({"cancelled"}),
    "client_approval": frozenset({"cancelled"}),
    "completed": frozenset(),
    "cancelled": frozenset({"backlog"}),
}
REVIEW_REQUIRED = (
    "This task requires review. Submit it for review instead of completing it directly."
)
NOT_FOUND = "This task doesn't exist or you don't have access to it."
TEAM_LEAD = "team_lead"


def _ref(user: User | None) -> UserRef | None:
    return UserRef(id=user.id, full_name=user.full_name) if user else None


def task_code(number: int) -> str:
    return f"T-{number}"


def is_overdue(task: Task, today: date) -> bool:
    return (
        task.due_date is not None and task.due_date < today and task.status not in CLOSED_STATUSES
    )


def task_item(row: TaskRow, today: date) -> TaskItem:
    task, project, client, assignee, _ = row
    return TaskItem(
        id=task.id,
        number=task.number,
        code=task_code(task.number),
        title=task.title,
        status=task.status,  # type: ignore[arg-type]  # DB check constraint
        status_label=STATUS_LABELS[task.status],
        project_id=project.id,
        project_name=project.name,
        client_id=client.id,
        client_name=client.name,
        assignee=_ref(assignee),
        due_date=task.due_date,
        overdue=is_overdue(task, today),
        requires_review=task.requires_review,
        requires_client_approval=task.requires_client_approval,
    )


def needs_review(task: Task) -> bool:
    """Work that goes to internal review or client approval can't be completed directly."""
    return task.requires_review or task.requires_client_approval


def can_manage(actor: Actor, project: Project) -> bool:
    return actor.is_super_admin or project.manager_id == actor.user_id or TEAM_LEAD in actor.roles


def can_work(actor: Actor, task: Task, project: Project) -> bool:
    return task.assignee_id == actor.user_id or can_manage(actor, project)


def next_statuses(actor: Actor, task: Task, project: Project) -> list[TaskStatus]:
    """Statuses this actor may move the task to now, in workflow order."""
    manage = can_manage(actor, project)
    if not (manage or can_work(actor, task, project)):
        return []
    allowed = set(TRANSITIONS[task.status])
    if not manage:
        allowed -= {"cancelled"}
        if task.status == "cancelled":
            allowed.clear()
    if needs_review(task):
        allowed.discard("completed")
    return [s for s in TASK_STATUSES if s in allowed]


class TaskService:
    def __init__(self, session: AsyncSession, *, clock: Clock) -> None:
        self._session = session
        self._repo = TaskRepository(session)
        self._projects = ProjectRepository(session)
        self._approvals = ApprovalRepository(session)
        self._clock = clock
        self._audit = AuditWriter(session)
        self._activity = ActivityRecorder(session)

    # ------------------------------------------------------------ reads

    async def list_tasks(
        self,
        actor: Actor,
        *,
        view: Literal["mine", "review", "all"],
        open_only: bool,
        assignee_id: uuid.UUID | None = None,
    ) -> list[TaskItem]:
        assignee = actor.user_id if view == "mine" else assignee_id
        reviewer = actor.user_id if view == "review" else None
        rows = await self._repo.list_tasks(
            actor, assignee=assignee, reviewer=reviewer, open_only=open_only
        )
        today = self._today()
        return [task_item(row, today) for row in rows]

    async def get(self, actor: Actor, task_id: uuid.UUID) -> TaskDetail:
        return await self._detail(actor, await self._visible(actor, task_id))

    async def assignee_options(self) -> list[UserRef]:
        return [
            UserRef(id=u.id, full_name=u.full_name) for u in await self._repo.assignable_users()
        ]

    # ------------------------------------------------------------ writes

    async def create(self, actor: Actor, data: TaskCreate) -> TaskDetail:
        if not actor.can(TASKS_CREATE):
            raise Forbidden("You don't have permission to create tasks.")
        found = await self._projects.get(actor, data.project_id)
        if found is None:
            raise NotFound("This project doesn't exist or you don't have access to it.")
        project, client, _ = found
        assignee = await self._assignee(data.assignee_id)

        task = Task(
            number=await next_value(self._session, "task"),
            project_id=project.id,
            client_id=client.id,
            title=data.title,
            description=data.description,
            status="ready" if assignee else "backlog",
            assignee_id=assignee.id if assignee else None,
            reviewer_id=project.manager_id,
            requires_review=data.requires_review,
            requires_client_approval=data.requires_client_approval,
            due_date=data.due_date,
            created_by_id=actor.user_id,
        )
        self._repo.add(task)
        await self._repo.flush()
        await self._log(
            actor,
            task,
            client,
            "task.created",
            f"Task {task_code(task.number)} created: {task.title}",
            changes={"title": task.title, "assignee_id": _str(task.assignee_id)},
        )
        return await self.get(actor, task.id)

    async def update(self, actor: Actor, task_id: uuid.UUID, data: TaskUpdate) -> TaskDetail:
        row = await self._visible(actor, task_id, lock=True)
        task, project, client, _, _ = row
        if not can_manage(actor, project):
            raise Forbidden("Only the project manager or a team lead can edit this task.")
        if task.status in CLOSED_STATUSES:
            raise BusinessRuleViolation("Closed tasks can't be edited.")

        incoming = data.model_dump(exclude_unset=True)
        if "title" in incoming and incoming["title"] is None:
            raise ValidationFailed("The task title can't be empty.")
        if incoming.get("assignee_id") is not None:
            await self._assignee(incoming["assignee_id"])
        if "reviewer_id" in incoming:
            if incoming["reviewer_id"] is None:
                raise ValidationFailed("A task must have a reviewer.")
            await self._assignee(incoming["reviewer_id"])

        changes: dict[str, Any] = {}
        for field, new in incoming.items():
            old = getattr(task, field)
            if old != new:
                changes[field] = [_jsonable(old), _jsonable(new)]
                setattr(task, field, new)
        if not changes:
            return await self._detail(actor, row)
        if "assignee_id" in changes and task.status == "backlog" and task.assignee_id:
            task.status = "ready"
        if "reviewer_id" in changes:
            # An open internal review moves to the new reviewer.
            request = await self._approvals.open_for_task(task.id, lock=True)
            if request is not None and request.stage == "internal":
                request.approver_id = task.reviewer_id
        await self._repo.flush()
        await self._log(
            actor,
            task,
            client,
            "task.updated",
            f"Task {task_code(task.number)} updated: "
            + ", ".join(f.replace("_id", "").replace("_", " ") for f in changes),
            changes=changes,
        )
        return await self.get(actor, task.id)

    async def change_status(
        self, actor: Actor, task_id: uuid.UUID, data: StatusChange
    ) -> TaskDetail:
        task, project, client, _, _ = await self._visible(actor, task_id, lock=True)
        target = data.status
        if not can_work(actor, task, project):
            raise Forbidden("Only the assignee or the project manager can move this task.")
        if target == task.status:
            raise BusinessRuleViolation(f"The task is already {STATUS_LABELS[target].lower()}.")
        if target == "completed" and needs_review(task):
            raise BusinessRuleViolation(REVIEW_REQUIRED)
        if target not in TRANSITIONS[task.status]:
            raise BusinessRuleViolation(
                f"A task can't move from {STATUS_LABELS[task.status]} to {STATUS_LABELS[target]}."
            )
        if (target == "cancelled" or task.status == "cancelled") and not can_manage(actor, project):
            raise Forbidden("Only the project manager or a team lead can cancel or reopen tasks.")

        previous = task.status
        if target == "cancelled":
            await self._approvals.cancel_open(task.id)
        task.status = target
        task.completed_at = self._clock.now() if target == "completed" else None
        await self._repo.flush()
        await self._log(
            actor,
            task,
            client,
            "task.status_changed",
            f"Task {task_code(task.number)} moved to {STATUS_LABELS[target]}: {task.title}",
            changes={"status": [previous, target]},
        )
        return await self.get(actor, task.id)

    # ------------------------------------------------------------ helpers

    def _today(self) -> date:
        return self._clock.now().date()

    async def _visible(self, actor: Actor, task_id: uuid.UUID, *, lock: bool = False) -> TaskRow:
        row = await self._repo.get(actor, task_id, lock=lock)
        if row is None:
            raise NotFound(NOT_FOUND)
        return row

    async def _assignee(self, user_id: uuid.UUID | None) -> User | None:
        if user_id is None:
            return None
        user = await self._repo.user(user_id)
        if user is None or not user.is_active or user.approved_at is None:
            raise ValidationFailed("Choose an active team member to assign.")
        return user

    async def _detail(self, actor: Actor, row: TaskRow) -> TaskDetail:
        task, project, client, _, reviewer = row
        item = task_item(row, self._today())
        versions = await self._approvals.versions(task.id)
        requests = await self._approvals.approvals(task.id)
        users = await self._approvals.users(
            [v.submitted_by_id for v in versions]
            + [a.decided_by_id for a in requests]
            + [a.approver_id for a in requests]
            + [a.requested_by_id for a in requests]
            + [client.account_manager_id]
        )
        pending = next((a for a in requests if a.status == "submitted"), None)
        blocked = decision_block(actor, self._open_request(pending, client)) if pending else None
        return TaskDetail(
            **item.model_dump(),
            description=task.description,
            reviewer=_ref(reviewer),
            created_at=task.created_at,
            completed_at=task.completed_at,
            permissions=TaskPermissions(
                work=can_work(actor, task, project),
                manage=can_manage(actor, project),
                next_statuses=next_statuses(actor, task, project),
                submit=can_work(actor, task, project)
                and task.status == "in_progress"
                and needs_review(task)
                and pending is None,
                decide=pending is not None and blocked is None,
                decide_blocked=blocked,
            ),
            versions=[_version_out(v, requests, users) for v in versions],
            open_approval=self._open_out(pending, versions, client, users) if pending else None,
            client_contact=client.contact_name,
        )

    @staticmethod
    def _open_request(request: Approval, client: Client) -> OpenRequest:
        return OpenRequest(
            stage=request.stage,
            approver_id=request.approver_id,
            requested_by_id=request.requested_by_id,
            client_manager_id=client.account_manager_id,
        )

    @staticmethod
    def _open_out(
        request: Approval,
        versions: list[TaskVersion],
        client: Client,
        users: dict[uuid.UUID, User],
    ) -> OpenApproval:
        version = next(v.number for v in versions if v.id == request.version_id)
        approver_id = (
            request.approver_id if request.stage == "internal" else client.account_manager_id
        )
        return OpenApproval(
            id=request.id,
            stage=request.stage,  # type: ignore[arg-type]  # DB check constraint
            version=version,
            approver=_ref(users.get(approver_id) if approver_id else None),
            requested_by=_ref(
                users.get(request.requested_by_id) if request.requested_by_id else None
            ),
            created_at=request.created_at,
        )

    async def _log(
        self,
        actor: Actor,
        task: Task,
        client: Client,
        action: str,
        summary: str,
        *,
        changes: dict[str, Any] | None = None,
    ) -> None:
        await self._audit.record(
            action=action,
            entity_type="task",
            entity_id=task.id,
            actor_user_id=actor.user_id,
            changes=changes,
            context={"code": task_code(task.number), "client_id": str(client.id)},
        )
        await self._activity.record(
            verb=action.removeprefix("task."),
            subject_type="client",
            subject_id=client.id,
            actor_user_id=actor.user_id,
            summary=summary,
        )


def feedback_author(request: Approval, users: dict[uuid.UUID, User]) -> str:
    if request.stage == "client":
        channel = CHANNEL_LABELS.get(request.client_channel or "", request.client_channel or "")
        return f"{request.client_decider} (client, via {channel})"
    decider = users.get(request.decided_by_id) if request.decided_by_id else None
    return decider.full_name if decider else "Unknown"


def _version_out(
    version: TaskVersion, requests: list[Approval], users: dict[uuid.UUID, User]
) -> VersionOut:
    decided = [
        r
        for r in requests
        if r.version_id == version.id and r.status in ("approved", "changes") and r.decided_at
    ]
    submitter = users.get(version.submitted_by_id) if version.submitted_by_id else None
    return VersionOut(
        number=version.number,
        note=version.note,
        link=version.link,
        submitted_by=_ref(submitter),
        submitted_at=version.submitted_at,
        feedback=[
            FeedbackOut(
                stage=r.stage,  # type: ignore[arg-type]  # DB check constraint
                result=r.status,  # type: ignore[arg-type]
                by=feedback_author(r, users),
                note=r.decision_note,
                at=r.decided_at,  # type: ignore[arg-type]  # filtered above
            )
            for r in decided
        ],
    )


def _jsonable(value: object) -> object:
    if isinstance(value, uuid.UUID | date):
        return str(value)
    return value


def _str(value: uuid.UUID | None) -> str | None:
    return str(value) if value else None
