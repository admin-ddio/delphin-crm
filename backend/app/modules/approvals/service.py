"""Review and approval of task work (rules from the clickable demo).

Flow
- the assignee (or a task manager) submits a version (note required, link
  optional) of an in-progress task that requires review or client approval;
- it goes to internal review (the task's reviewer) if the task requires review,
  otherwise straight to client approval;
- an internal approval of a task that also needs client approval opens the
  client stage (same version); any other approval completes the task;
- "request changes" needs feedback and sends the task back to In progress;
- client decisions are recorded by the client's Account Manager with who at the
  client decided and how they told us;
- nobody approves their own submission, and a reviewer can't submit work they
  would review themselves (Super Admin excepted);
- every step is audited and appears on the client's activity timeline.

TODO(pilot-port): confirm against services/approvals.ts.
"""

from __future__ import annotations

import uuid
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.actor import Actor
from app.core.clock import Clock
from app.core.errors import BusinessRuleViolation, Forbidden, NotFound, ValidationFailed
from app.modules.approvals.models import Approval, TaskVersion
from app.modules.approvals.repository import ApprovalRepository, ApprovalRow
from app.modules.approvals.rules import STAGE_LABELS, OpenRequest, decision_block
from app.modules.approvals.schemas import ApprovalItem, DecisionIn, SubmitIn
from app.modules.clients.models import Client
from app.modules.notifications.service import NotificationService
from app.modules.tasks.models import Task
from app.modules.tasks.repository import TaskRepository
from app.modules.tasks.schemas import TaskDetail, UserRef
from app.modules.tasks.service import (
    TaskService,
    can_work,
    feedback_author,
    needs_review,
    task_code,
)
from app.platform.activity.service import ActivityRecorder
from app.platform.audit.service import AuditWriter
from app.platform.identity.models import User
from app.platform.notifications.interfaces import NotificationRequest

NOT_FOUND = "This approval doesn't exist or you don't have access to it."


def _ref(user: User | None) -> UserRef | None:
    return UserRef(id=user.id, full_name=user.full_name) if user else None


class ApprovalService:
    def __init__(self, session: AsyncSession, *, clock: Clock) -> None:
        self._repo = ApprovalRepository(session)
        self._tasks = TaskRepository(session)
        self._task_service = TaskService(session, clock=clock)
        self._clock = clock
        self._audit = AuditWriter(session)
        self._activity = ActivityRecorder(session)
        self._notifier = NotificationService(session)

    # ------------------------------------------------------------ reads

    async def list_approvals(
        self, actor: Actor, view: Literal["mine", "all"]
    ) -> list[ApprovalItem]:
        return [self._item(row) for row in await self._repo.list_approvals(actor, view=view)]

    async def get(self, actor: Actor, approval_id: uuid.UUID) -> ApprovalItem:
        row = await self._repo.get(actor, approval_id)
        if row is None:
            raise NotFound(NOT_FOUND)
        return self._item(row)

    # ------------------------------------------------------------ submit

    async def submit(self, actor: Actor, data: SubmitIn) -> TaskDetail:
        row = await self._tasks.get(actor, data.task_id, lock=True)
        if row is None:
            raise NotFound("This task doesn't exist or you don't have access to it.")
        task, project, client, _, _ = row
        if not can_work(actor, task, project):
            raise Forbidden("Only the assignee or the project manager can submit this task.")
        if not needs_review(task):
            raise BusinessRuleViolation("This task doesn't need review. Mark it completed instead.")
        if task.status in ("internal_review", "client_approval"):
            raise BusinessRuleViolation("This task is already waiting for a decision.")
        if task.status != "in_progress":
            raise BusinessRuleViolation("Start work on the task before submitting it for review.")
        if not data.note:
            raise ValidationFailed("Describe what changed for the reviewer.")
        stage = "internal" if task.requires_review else "client"
        if stage == "internal":
            if task.reviewer_id is None:
                raise BusinessRuleViolation("Set a reviewer before submitting for review.")
            if task.reviewer_id == actor.user_id and not actor.is_super_admin:
                raise BusinessRuleViolation(
                    "You can't review your own work. Ask the PM to set another reviewer."
                )

        version = TaskVersion(
            task_id=task.id,
            number=await self._repo.next_version_number(task.id),
            note=data.note,
            link=data.link,
            submitted_by_id=actor.user_id,
        )
        self._repo.add(version)
        await self._repo.flush()
        request = Approval(
            task_id=task.id,
            version_id=version.id,
            client_id=client.id,
            stage=stage,
            approver_id=task.reviewer_id if stage == "internal" else None,
            requested_by_id=actor.user_id,
        )
        self._repo.add(request)
        previous = task.status
        task.status = "internal_review" if stage == "internal" else "client_approval"
        await self._repo.flush()
        await self._log(
            actor,
            task,
            client,
            "approval.submitted",
            f'"{task.title}" v{version.number} submitted for {STAGE_LABELS[stage]}',
            changes={"status": [previous, task.status], "version": version.number},
        )
        approver = task.reviewer_id if stage == "internal" else client.account_manager_id
        await self._notifier.notify_many(
            [approver],
            NotificationRequest(
                user_id=actor.user_id,
                kind="approval.requested",
                title=f"Awaiting your {STAGE_LABELS[stage]}: {task.title} v{version.number}",
                body=client.name,
                link=f"/approvals?task={task.id}",
                entity_type="task",
                entity_id=str(task.id),
            ),
            exclude=actor.user_id,
        )
        return await self._task_service.get(actor, task.id)

    # ------------------------------------------------------------ decide

    async def decide(self, actor: Actor, approval_id: uuid.UUID, data: DecisionIn) -> TaskDetail:
        found = await self._repo.get(actor, approval_id)
        if found is None:
            raise NotFound(NOT_FOUND)
        request, version, task, client, _, _, _ = found
        locked = await self._tasks.get(actor, task.id, lock=True)
        current = await self._repo.open_for_task(task.id, lock=True)
        if locked is None or current is None or current.id != request.id:
            raise BusinessRuleViolation("This request has already been decided.")

        block = decision_block(
            actor,
            OpenRequest(
                stage=request.stage,
                approver_id=request.approver_id,
                requested_by_id=request.requested_by_id,
                client_manager_id=client.account_manager_id,
            ),
        )
        if block:
            raise Forbidden(block)
        if data.decision == "changes" and not data.note:
            raise ValidationFailed("Add feedback explaining the requested changes.")
        if request.stage == "client":
            if not data.client_decider:
                raise ValidationFailed("Record who at the client made this decision.")
            if data.client_channel is None:
                raise ValidationFailed("Record how the client communicated the decision.")
            request.client_decider = data.client_decider
            request.client_channel = data.client_channel

        now = self._clock.now()
        request.status = data.decision
        request.decided_by_id = actor.user_id
        request.decided_at = now
        request.decision_note = data.note
        users = await self._repo.users([actor.user_id])
        by = feedback_author(request, users)
        label = f'"{task.title}" v{version.number}'
        previous = task.status

        if (
            data.decision == "approved"
            and request.stage == "internal"
            and (task.requires_client_approval)
        ):
            self._repo.add(
                Approval(
                    task_id=task.id,
                    version_id=version.id,
                    client_id=client.id,
                    stage="client",
                    requested_by_id=version.submitted_by_id,
                )
            )
            task.status = "client_approval"
            action, summary = (
                "approval.approved",
                f"{label} approved internally by {by}; client approval requested",
            )
        elif data.decision == "approved":
            task.status = "completed"
            task.completed_at = now
            action, summary = "approval.approved", f"{by} approved {label}; task completed"
        else:
            task.status = "in_progress"
            action, summary = "approval.changes_requested", f"{by} requested changes to {label}"

        await self._repo.flush()
        await self._log(
            actor,
            task,
            client,
            action,
            summary,
            changes={"status": [previous, task.status], "stage": request.stage},
        )
        await self._notifier.notify_many(
            [version.submitted_by_id],
            NotificationRequest(
                user_id=actor.user_id,
                kind="approval.decided",
                title=f"{summary[0].upper()}{summary[1:]}",
                link=f"/tasks?view=all&task={task.id}",
                entity_type="task",
                entity_id=str(task.id),
            ),
            exclude=actor.user_id,
        )
        return await self._task_service.get(actor, task.id)

    # ------------------------------------------------------------ helpers

    @staticmethod
    def _item(row: ApprovalRow) -> ApprovalItem:
        request, version, task, client, approver, requester, manager = row
        return ApprovalItem(
            id=request.id,
            task_id=task.id,
            task_code=task_code(task.number),
            task_title=task.title,
            client_id=client.id,
            client_name=client.name,
            stage=request.stage,  # type: ignore[arg-type]  # DB check constraint
            version=version.number,
            status=request.status,  # type: ignore[arg-type]
            approver=_ref(approver if request.stage == "internal" else manager),
            requested_by=_ref(requester),
            created_at=request.created_at,
            decided_at=request.decided_at,
        )

    async def _log(
        self,
        actor: Actor,
        task: Task,
        client: Client,
        action: str,
        summary: str,
        *,
        changes: dict[str, object],
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
            verb=action.removeprefix("approval."),
            subject_type="client",
            subject_id=client.id,
            actor_user_id=actor.user_id,
            summary=summary,
        )
