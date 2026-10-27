"""Team & Roles: sign-in accounts (services plan, 2026-10-27; demo "Team & Roles").

Rules
- the hub lists every sign-in account with its roles, linked employee, status and
  workload (open / overdue tasks); visible with `users.manage`, `org.roles.assign`,
  `users.approve` or `org.team.view`;
- `users.manage` invites people (account here and in Firebase, roles, optional
  employee link) and deactivates / reactivates accounts; a one-time password-setup
  link is returned because e-mail sending isn't configured;
- roles given on invitation must be within the inviter's authority (as in role
  assignment); nobody deactivates themself or anyone holding roles above them;
- deactivating revokes every session at once; everything is audited.
TODO(pilot-port): confirm against the pilot's Team & Roles page.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.actor import Actor
from app.authz.permissions import ORG_ROLES_ASSIGN, ORG_TEAM_VIEW, USERS_APPROVE, USERS_MANAGE
from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import Conflict, Forbidden, NotFound, ValidationFailed
from app.modules.auth.service import AuthService
from app.modules.tasks.models import CLOSED_STATUSES, Task
from app.modules.team.models import Employee
from app.modules.team.repository import RoleRepository
from app.modules.team.schemas import (
    Account,
    AccountsOverview,
    InviteRequest,
    InviteResult,
    PersonRef,
)
from app.modules.team.service.org import within_authority
from app.platform.audit.service import AuditWriter
from app.platform.identity.firebase import IdentityProvider
from app.platform.identity.models import Role, User, UserRole
from app.platform.identity.sessions import SessionStore


def _status(user: User) -> str:
    if not user.is_active:
        return "deactivated"
    if user.approved_at is None:
        return "pending"
    if user.last_login_at is None:
        return "invited"
    return "active"


class AccountsService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        clock: Clock,
        settings: Settings,
        identity: IdentityProvider,
    ) -> None:
        self._session = session
        self._roles = RoleRepository(session)
        self._clock = clock
        self._settings = settings
        self._identity = identity
        self._audit = AuditWriter(session)

    async def overview(self, actor: Actor) -> AccountsOverview:
        if not actor.can_any(USERS_MANAGE, ORG_ROLES_ASSIGN, USERS_APPROVE, ORG_TEAM_VIEW):
            raise Forbidden("You can't see the team's accounts.")
        users = list((await self._session.execute(select(User).order_by(User.full_name))).scalars())
        return AccountsOverview(
            accounts=await self._accounts(actor, users),
            can_invite=actor.can(USERS_MANAGE),
            can_assign_roles=actor.can(ORG_ROLES_ASSIGN),
            can_approve=actor.can(USERS_APPROVE),
            can_deactivate=actor.can(USERS_MANAGE),
        )

    async def invite(self, actor: Actor, data: InviteRequest) -> InviteResult:
        if not actor.can(USERS_MANAGE):
            raise Forbidden("You can't invite people.")
        roles = {r.key: r for r in await self._roles.roles()}
        wanted = list(dict.fromkeys(data.roles))
        unknown = [k for k in wanted if k not in roles]
        if unknown:
            raise ValidationFailed(f"Unknown role '{unknown[0]}'.", details={"roles": unknown})
        above = [roles[k].name for k in wanted if not within_authority(actor, roles[k])]
        if above:
            raise Forbidden(f"You can't give {above[0]}: it has permissions you don't hold.")
        employee = None
        if data.employee_id is not None:
            employee = await self._session.get(Employee, data.employee_id)
            if employee is None or employee.status == "exited":
                raise ValidationFailed("Choose a current employee to link.")
            if employee.user_id is not None:
                raise Conflict(f"{employee.full_name} already has a sign-in account.")
        auth = AuthService(
            self._session, clock=self._clock, settings=self._settings, identity=self._identity
        )
        invitation = await auth.invite(
            email=str(data.email),
            full_name=data.full_name,
            role_key=wanted[0],
            invited_by=actor.user_id,
        )
        user = invitation.user
        for key in wanted[1:]:
            self._session.add(
                UserRole(user_id=user.id, role_id=roles[key].id, assigned_by_id=actor.user_id)
            )
        if employee is not None:
            employee.user_id = user.id
        await self._session.flush()
        await self._audit.record(
            action="user.invited",
            entity_type="user",
            entity_id=user.id,
            actor_user_id=actor.user_id,
            changes={"roles": wanted, "employee_id": str(employee.id) if employee else None},
            context={"name": user.full_name, "email": user.email},
        )
        (account,) = await self._accounts(actor, [user])
        return InviteResult(account=account, setup_link=invitation.link)

    async def set_active(self, actor: Actor, user_id: uuid.UUID, *, active: bool) -> Account:
        if not actor.can(USERS_MANAGE):
            raise Forbidden("You can't deactivate or reactivate accounts.")
        if user_id == actor.user_id:
            raise Forbidden("You can't deactivate or reactivate your own account.")
        user = await self._session.get(User, user_id, with_for_update=True)
        if user is None:
            raise NotFound("This account doesn't exist.")
        if not all(within_authority(actor, role) for role in await self._held(user.id)):
            raise Forbidden("This account holds a role above your authority.")
        if user.is_active != active:
            user.is_active = active
            if not active:
                ttl = timedelta(hours=self._settings.session_ttl_hours)
                await SessionStore(self._session, self._clock, ttl).revoke_all(user.id)
            await self._session.flush()
            await self._audit.record(
                action="user.reactivated" if active else "user.deactivated",
                entity_type="user",
                entity_id=user.id,
                actor_user_id=actor.user_id,
                changes={"is_active": [not active, active]},
                context={"name": user.full_name, "email": user.email},
            )
        (account,) = await self._accounts(actor, [user])
        return account

    # ------------------------------------------------------------ helpers

    async def _held(self, user_id: uuid.UUID) -> list[Role]:
        rows = await self._session.execute(
            select(Role)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id)
        )
        return list(rows.scalars())

    async def _accounts(self, actor: Actor, users: list[User]) -> list[Account]:
        ids = [u.id for u in users]
        roles = {r.id: r for r in await self._roles.roles()}
        held: dict[uuid.UUID, list[Role]] = defaultdict(list)
        pairs = await self._session.execute(
            select(UserRole.user_id, UserRole.role_id).where(UserRole.user_id.in_(ids))
        )
        for user_id, role_id in pairs.all():
            if role_id in roles:
                held[user_id].append(roles[role_id])
        linked = await self._session.execute(select(Employee).where(Employee.user_id.in_(ids)))
        employees = {e.user_id: e for e in linked.scalars()}
        today = self._clock.now().date()
        counts = await self._session.execute(
            select(Task.assignee_id, func.count(), func.count().filter(Task.due_date < today))
            .where(Task.assignee_id.in_(ids), Task.status.not_in(CLOSED_STATUSES))
            .group_by(Task.assignee_id)
        )
        workload = {assignee: (int(total), int(late)) for assignee, total, late in counts.all()}
        result = []
        for user in users:
            employee = employees.get(user.id)
            total, overdue = workload.get(user.id, (0, 0))
            result.append(
                Account(
                    id=user.id,
                    full_name=user.full_name,
                    email=user.email,
                    status=_status(user),  # type: ignore[arg-type]
                    roles=sorted(r.key for r in held[user.id]),
                    employee=PersonRef(
                        id=employee.id, code=employee.code, full_name=employee.full_name
                    )
                    if employee
                    else None,
                    last_login_at=user.last_login_at,
                    open_tasks=total,
                    overdue_tasks=overdue,
                    is_me=user.id == actor.user_id,
                    editable=user.id != actor.user_id
                    and actor.can_any(USERS_MANAGE, ORG_ROLES_ASSIGN)
                    and all(within_authority(actor, r) for r in held[user.id]),
                )
            )
        return result
