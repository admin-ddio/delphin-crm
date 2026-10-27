"""Organization & Role Settings: reporting relationships, the org chart, role
definitions and role assignments, and the organisation audit log.

Rules (Organization brief §6–8):
- reporting lines are typed (seven kinds), dated and never deleted; a change ends the
  lines that go away (`ends_on` = effective date) and starts the new ones;
- one open line per single-valued kind; functional and project lines may be several,
  never the same manager (and project) twice; nobody reports to themself or to a
  former employee; no loops through direct and functional lines;
- `org.reporting.manage` edits every kind; `org.projects.assign` alone edits Project
  Manager lines only. Project lines point at existing projects;
- previews validate and return the chart as it would be, without saving;
- role definitions (`org.roles.manage`) and assignments (`org.roles.assign`) can never
  raise anyone above the actor: granted permissions must be ones the actor holds,
  the wildcard is never granted, nobody edits Super Admin, a role they hold, or their
  own roles. Designations never grant permissions;
- every change is audited; `org.audit.view` reads the organisation audit log.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import date

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.actor import Actor
from app.authz.permissions import (
    CATALOGUE,
    ORG_AUDIT_VIEW,
    ORG_PROJECTS_ASSIGN,
    ORG_REPORTING_MANAGE,
    ORG_ROLES_ASSIGN,
    ORG_ROLES_MANAGE,
    ORG_VIEW,
    PERMISSION_INFO,
    SUPER_ADMIN,
    WILDCARD,
)
from app.core.clock import Clock, business_today
from app.core.errors import Conflict, Forbidden, NotFound, ValidationFailed
from app.modules.team.models import Employee, EmploymentEvent, ReportingLine
from app.modules.team.repository import OrgAuditRepository, PeopleRepository, RoleRepository
from app.modules.team.schemas import (
    ChartDepartment,
    ChartMember,
    DeliveryGroup,
    DeliveryProject,
    LineChange,
    OrgAuditEntry,
    OrgChart,
    PermissionInfo,
    PersonRef,
    ProjectOption,
    ProjectRef,
    Ref,
    Reporting,
    ReportingChange,
    ReportingLineIn,
    ReportingLineOut,
    ReportingPreview,
    RoleIn,
    RoleOut,
    RolesOverview,
    RoleUpdate,
    UserRoles,
    UserRolesUpdate,
)
from app.modules.team.service.people import (
    EMPLOYEE_NOT_FOUND,
    STATUS_LABELS,
    load_org,
    require,
    visible_projects,
)
from app.modules.team.service.structure import KIND_LABELS, SINGLE_KINDS, Org, project_ref
from app.platform.audit.service import AuditWriter
from app.platform.identity.models import Role

Key = tuple[str, uuid.UUID, uuid.UUID | None]


def within_authority(actor: Actor, role: Role) -> bool:
    """The role grants nothing the actor doesn't hold (Super Admin holds everything)."""
    if actor.is_super_admin:
        return True
    return WILDCARD not in role.permissions and set(role.permissions) <= actor.permissions


def _key(line: ReportingLine | ReportingLineIn) -> Key:
    return line.kind, line.manager_id, line.project_id


class OrgService:
    def __init__(self, session: AsyncSession, *, clock: Clock) -> None:
        self._people = PeopleRepository(session)
        self._roles = RoleRepository(session)
        self._audit_log = OrgAuditRepository(session)
        self._clock = clock
        self._audit = AuditWriter(session)

    # ================================================================ reporting

    async def reporting(self, actor: Actor, employee_id: uuid.UUID) -> Reporting:
        require(actor, ORG_VIEW, "You can't see the organisation structure.")
        org = await load_org(self._people)
        employee = self._find(org, employee_id)
        projects = await visible_projects(self._people, actor)
        history = await self._people.lines_for(employee.id)
        users = await self._people.users(
            {i for ln in history for i in (ln.created_by_id, ln.ended_by_id) if i}
        )

        def out(line: ReportingLine) -> ReportingLineOut:
            created = users.get(line.created_by_id) if line.created_by_id else None
            ended = users.get(line.ended_by_id) if line.ended_by_id else None
            return ReportingLineOut(
                id=line.id,
                kind=line.kind,  # type: ignore[arg-type]  # DB check constraint
                kind_label=KIND_LABELS[line.kind],
                manager=org.person(line.manager_id)
                or PersonRef(id=line.manager_id, code="", full_name="—"),
                project=project_ref(line.project_id, projects),
                starts_on=line.starts_on,
                ends_on=line.ends_on,
                active=line.ends_on is None,
                created_by=created.full_name if created else None,
                ended_by=ended.full_name if ended else None,
            )

        department = org.department_of(employee)
        return Reporting(
            employee=org.person(employee.id),  # type: ignore[arg-type]
            department=Ref(id=department.id, name=department.name) if department else None,
            lines=[out(ln) for ln in history if ln.ends_on is None],
            effective=org.relations(employee, projects),
            history=[out(ln) for ln in history],
            can_edit=actor.can_any(ORG_REPORTING_MANAGE, ORG_PROJECTS_ASSIGN),
            projects_only=not actor.can(ORG_REPORTING_MANAGE),
        )

    async def preview(
        self, actor: Actor, employee_id: uuid.UUID, change: ReportingChange
    ) -> ReportingPreview:
        self._require_edit(actor)
        org = await load_org(self._people)
        employee = self._find(org, employee_id)
        projects = await visible_projects(self._people, actor)
        errors, added, ended, after = await self._plan(actor, org, employee, change)
        shown = after if not errors else org
        return ReportingPreview(
            valid=not errors,
            errors=errors,
            added=[self._line_change(org, k, projects) for k in added],
            ended=[self._line_change(org, _key(ln), projects) for ln in ended],
            effective=shown.relations(employee, projects),
            chart=self._chart(shown, projects),
        )

    async def change_reporting(
        self, actor: Actor, employee_id: uuid.UUID, change: ReportingChange
    ) -> Reporting:
        self._require_edit(actor)
        org = await load_org(self._people)
        employee = self._find(org, employee_id)
        errors, added, ended, _ = await self._plan(actor, org, employee, change)
        if errors:
            raise ValidationFailed(errors[0], details={"errors": errors})
        if not (added or ended):
            return await self.reporting(actor, employee.id)
        effective_on = change.effective_on or self._today()
        for line in ended:
            line.ends_on = effective_on
            line.ended_by_id = actor.user_id
        try:
            await self._people.flush()
            for kind, manager_id, project_id in added:
                self._people.add(
                    ReportingLine(
                        employee_id=employee.id,
                        manager_id=manager_id,
                        kind=kind,
                        project_id=project_id,
                        starts_on=effective_on,
                        created_by_id=actor.user_id,
                    )
                )
            await self._people.flush()
        except IntegrityError as exc:  # a concurrent change won the race
            raise Conflict("Someone else changed these reporting lines. Reload and retry.") from exc

        projects = await visible_projects(self._people, actor)
        summary = "; ".join(
            [f"{KIND_LABELS[k]}: {org.name(m)} added" for k, m, _ in added]
            + [f"{KIND_LABELS[ln.kind]}: {org.name(ln.manager_id)} ended" for ln in ended]
        )
        self._people.add(
            EmploymentEvent(
                employee_id=employee.id,
                kind="reporting_changed",
                summary=f"Reporting changed — {summary}",
                effective_on=effective_on,
                actor_user_id=actor.user_id,
            )
        )
        await self._audit.record(
            action="reporting.changed",
            entity_type="employee",
            entity_id=employee.id,
            actor_user_id=actor.user_id,
            changes={
                "added": [
                    self._line_change(org, k, projects).model_dump(mode="json") for k in added
                ],
                "ended": [
                    self._line_change(org, _key(ln), projects).model_dump(mode="json")
                    for ln in ended
                ],
                "effective_on": str(effective_on),
            },
            context={"code": employee.code, "name": employee.full_name},
        )
        await self._people.flush()
        return await self.reporting(actor, employee.id)

    async def project_options(self, actor: Actor) -> list[ProjectOption]:
        self._require_edit(actor)
        org = await load_org(self._people)
        by_user = {e.user_id: e for e in org.employees.values() if e.user_id}
        visible = await visible_projects(self._people, actor)
        return [
            ProjectOption(
                id=p.id,
                code=p.code,
                name=p.name,
                manager=org.person(by_user[p.manager_id].id) if p.manager_id in by_user else None,
            )
            for p in await self._people.projects()
            if p.id in visible
        ]

    # ================================================================ org chart

    async def chart(self, actor: Actor) -> OrgChart:
        require(actor, ORG_VIEW, "You can't see the organisation structure.")
        org = await load_org(self._people)
        return self._chart(org, await visible_projects(self._people, actor))

    # ================================================================ roles

    async def roles(self, actor: Actor) -> RolesOverview:
        if not actor.can_any(ORG_ROLES_MANAGE, ORG_ROLES_ASSIGN):
            raise Forbidden("You can't see role settings.")
        counts = await self._roles.member_counts()
        return RolesOverview(
            catalogue=[
                PermissionInfo(key=key, module=module, label=label)
                for key, (module, label) in PERMISSION_INFO.items()
            ],
            roles=[
                self._role_out(actor, role, counts.get(role.id, 0))
                for role in await self._roles.roles()
            ],
            can_manage=actor.can(ORG_ROLES_MANAGE),
            can_assign=actor.can(ORG_ROLES_ASSIGN),
        )

    async def create_role(self, actor: Actor, data: RoleIn) -> RoleOut:
        require(actor, ORG_ROLES_MANAGE, "You can't manage role definitions.")
        if await self._roles.role(data.key):
            raise Conflict(f"A role with the key {data.key} already exists.")
        permissions = self._grantable(actor, data.permissions)
        role = Role(
            key=data.key,
            name=data.name,
            description=data.description,
            permissions=permissions,
            is_system=False,
        )
        self._roles.add(role)
        await self._roles.flush()
        await self._audit.record(
            action="role.created",
            entity_type="role",
            entity_id=role.id,
            actor_user_id=actor.user_id,
            changes={"key": role.key, "name": role.name, "permissions": permissions},
            context={"name": role.name},
        )
        return self._role_out(actor, role, 0)

    async def update_role(self, actor: Actor, key: str, data: RoleUpdate) -> RoleOut:
        require(actor, ORG_ROLES_MANAGE, "You can't manage role definitions.")
        role = await self._roles.role(key, lock=True)
        if role is None:
            raise NotFound("This role doesn't exist.")
        self._check_role_editable(actor, role)
        incoming = data.model_dump(exclude_unset=True)
        changes: dict[str, object] = {}
        if incoming.get("name") is not None and incoming["name"] != role.name:
            changes["name"] = [role.name, incoming["name"]]
            role.name = incoming["name"]
        if "description" in incoming and incoming["description"] != role.description:
            changes["description"] = [role.description, incoming["description"]]
            role.description = incoming["description"]
        if incoming.get("permissions") is not None:
            permissions = self._grantable(actor, incoming["permissions"])
            old = sorted(role.permissions)
            if permissions != old:
                changes["added"] = sorted(set(permissions) - set(old))
                changes["removed"] = sorted(set(old) - set(permissions))
                role.permissions = permissions
        if changes:
            await self._roles.flush()
            await self._audit.record(
                action="role.updated",
                entity_type="role",
                entity_id=role.id,
                actor_user_id=actor.user_id,
                changes=changes,
                context={"key": role.key, "name": role.name},
            )
        counts = await self._roles.member_counts()
        return self._role_out(actor, role, counts.get(role.id, 0))

    async def users(self, actor: Actor) -> list[UserRoles]:
        require(actor, ORG_ROLES_ASSIGN, "You can't assign roles.")
        org = await load_org(self._people)
        by_user = {e.user_id: e for e in org.employees.values() if e.user_id}
        roles = {r.key: r for r in await self._roles.roles()}
        held: dict[uuid.UUID, list[str]] = defaultdict(list)
        for user_id, key in await self._roles.assignments():
            held[user_id].append(key)
        result = []
        for user in await self._roles.users():
            keys = sorted(held[user.id])
            employee = by_user.get(user.id)
            result.append(
                UserRoles(
                    id=user.id,
                    full_name=user.full_name,
                    email=user.email,
                    roles=keys,
                    employee=org.person(employee.id) if employee else None,
                    editable=user.id != actor.user_id
                    and all(within_authority(actor, roles[k]) for k in keys if k in roles),
                )
            )
        return result

    async def set_user_roles(
        self, actor: Actor, user_id: uuid.UUID, data: UserRolesUpdate
    ) -> UserRoles:
        require(actor, ORG_ROLES_ASSIGN, "You can't assign roles.")
        if user_id == actor.user_id:
            raise Forbidden("You can't change your own roles.")
        user = await self._roles.user(user_id)
        if user is None or not user.is_active or user.approved_at is None:
            raise NotFound("This user doesn't exist or isn't approved yet.")
        roles = {r.key: r for r in await self._roles.roles()}
        current = sorted(k for u, k in await self._roles.assignments() if u == user_id)
        if not all(within_authority(actor, roles[k]) for k in current if k in roles):
            raise Forbidden("This user holds a role above your authority.")
        wanted = sorted(set(data.roles))
        unknown = [k for k in wanted if k not in roles]
        if unknown:
            raise ValidationFailed(f"Unknown role '{unknown[0]}'.", details={"roles": unknown})
        above = [roles[k].name for k in wanted if not within_authority(actor, roles[k])]
        if above:
            raise Forbidden(f"You can't assign {above[0]}: it has permissions you don't hold.")
        if wanted != current:
            await self._roles.set_roles(user_id, [roles[k] for k in wanted], actor.user_id)
            await self._audit.record(
                action="user.roles_changed",
                entity_type="user",
                entity_id=user_id,
                actor_user_id=actor.user_id,
                changes={"roles": [current, wanted]},
                context={"name": user.full_name, "email": user.email},
            )
        return next(u for u in await self.users(actor) if u.id == user_id)

    # ================================================================ audit

    async def audit(
        self, actor: Actor, *, limit: int = 200, action: str | None = None
    ) -> list[OrgAuditEntry]:
        require(actor, ORG_AUDIT_VIEW, "You can't see the organisation audit log.")
        return [
            OrgAuditEntry(
                id=entry.id,
                occurred_at=entry.occurred_at,
                actor=user.full_name if user else None,
                action=entry.action,
                entity_type=entry.entity_type,
                entity_id=entry.entity_id,
                changes=entry.changes,
                context=entry.context,
            )
            for entry, user in await self._audit_log.entries(limit=limit, action=action)
        ]

    # ================================================================ helpers

    def _today(self) -> date:
        return business_today(self._clock)

    @staticmethod
    def _find(org: Org, employee_id: uuid.UUID) -> Employee:
        employee = org.employees.get(employee_id)
        if employee is None:
            raise NotFound(EMPLOYEE_NOT_FOUND)
        return employee

    @staticmethod
    def _require_edit(actor: Actor) -> None:
        if not actor.can_any(ORG_REPORTING_MANAGE, ORG_PROJECTS_ASSIGN):
            raise Forbidden("You can't change reporting relationships.")

    async def _plan(  # noqa: PLR0912  # one check per rule of the brief
        self, actor: Actor, org: Org, employee: Employee, change: ReportingChange
    ) -> tuple[list[str], list[Key], list[ReportingLine], Org]:
        """Validate a change: (errors, lines to add, lines to end, org afterwards)."""
        errors: list[str] = []
        today = self._today()
        effective_on = change.effective_on or today
        current = {_key(ln): ln for ln in org.by_employee.get(employee.id, [])}
        wanted: dict[Key, ReportingLineIn] = {}
        for line in change.lines:
            label = KIND_LABELS[line.kind]
            if _key(line) in wanted:
                errors.append(f"{label}: {org.name(line.manager_id)} is listed twice.")
            wanted[_key(line)] = line
            if line.manager_id == employee.id:
                errors.append(f"{label}: an employee can't report to themselves.")
            elif not org.active(line.manager_id):
                errors.append(f"{label}: choose a current employee.")
            if line.project_id is not None:
                if line.kind != "project_manager":
                    errors.append(f"{label}: only Project Manager lines can name a project.")
                elif await self._people.project(line.project_id) is None:
                    errors.append(f"{label}: that project doesn't exist.")
        for kind in SINGLE_KINDS:
            if sum(1 for k in wanted if k[0] == kind) > 1:
                errors.append(f"Only one {KIND_LABELS[kind].lower()} at a time.")

        added = [k for k in wanted if k not in current]
        ended = [ln for k, ln in current.items() if k not in wanted]
        if not actor.can(ORG_REPORTING_MANAGE) and any(
            k[0] != "project_manager" for k in [*added, *(_key(ln) for ln in ended)]
        ):
            raise Forbidden("You can only change Project Manager assignments.")
        if effective_on > today:
            errors.append("The effective date can't be in the future.")
        late = [ln for ln in ended if ln.starts_on > effective_on]
        if late:
            errors.append(
                f"The effective date can't be before {late[0].starts_on:%d %b %Y}, "
                f"when the {KIND_LABELS[late[0].kind].lower()} line started."
            )

        after = org.with_lines(
            employee.id,
            [ln for k, ln in current.items() if k in wanted]
            + [
                ReportingLine(
                    employee_id=employee.id,
                    manager_id=m,
                    kind=k,
                    project_id=p,
                    starts_on=effective_on,
                )
                for k, m, p in added
            ],
        )
        if not errors:
            loop = after.loop_through(employee.id)
            if loop:
                errors.append(after.loop_message(loop))
        return errors, added, ended, after

    @staticmethod
    def _line_change(org: Org, key: Key, projects: dict[uuid.UUID, ProjectRef]) -> LineChange:
        kind, manager_id, project_id = key
        return LineChange(
            kind=kind,  # type: ignore[arg-type]
            kind_label=KIND_LABELS[kind],
            manager=org.person(manager_id) or PersonRef(id=manager_id, code="", full_name="—"),
            project=project_ref(project_id, projects),
        )

    def _chart(self, org: Org, projects: dict[uuid.UUID, ProjectRef]) -> OrgChart:
        current = sorted(
            (e for e in org.employees.values() if e.status != "exited"),
            key=lambda e: e.full_name,
        )

        def member(employee: Employee) -> ChartMember:
            designation = (
                org.designations.get(employee.designation_id) if employee.designation_id else None
            )
            relations = org.relations(employee, projects)
            issues = []
            if not employee.is_executive and not any(
                r.kind == "functional_manager" for r in relations
            ):
                issues.append("No functional manager")
            return ChartMember(
                id=employee.id,
                code=employee.code,
                full_name=employee.full_name,
                designation=Ref(id=designation.id, name=designation.name) if designation else None,
                department_id=org.department_id_of(employee),
                status=employee.status,  # type: ignore[arg-type]
                status_label=STATUS_LABELS[employee.status],
                is_executive=employee.is_executive,
                relations=relations,
                issues=issues,
            )

        departments = []
        for department in org.departments.values():
            owners = org.people(org.owners.get(department.id, []))
            issues = []
            if not owners:
                issues.append("No executive owner")
            if department.head_id is None:
                issues.append("No department head")
            if department.delivery_manager_id is None:
                issues.append("No default project manager")
            departments.append(
                ChartDepartment(
                    id=department.id,
                    name=department.name,
                    description=department.description,
                    is_active=department.is_active,
                    head=org.person(department.head_id),
                    owners=owners,
                    delivery_manager=org.person(department.delivery_manager_id),
                    members=[
                        member(e)
                        for e in current
                        if org.department_id_of(e) == department.id and not e.is_executive
                    ],
                    issues=issues if department.is_active else [],
                )
            )

        # Delivery: every effective Project Manager relation, grouped by PM and project.
        groups: dict[uuid.UUID, dict[uuid.UUID | None, list[PersonRef]]] = defaultdict(
            lambda: defaultdict(list)
        )
        for employee in current:
            for r in org.resolve_kind(employee, "project_manager"):
                groups[r.manager_id][r.project_id].append(org.person(employee.id))  # type: ignore[arg-type]
        delivery = []
        for manager_id in sorted(groups, key=org.name):
            manager = org.person(manager_id)
            if manager is None:
                continue
            by_project = groups[manager_id]
            delivery.append(
                DeliveryGroup(
                    manager=manager,
                    members=by_project.get(None, []),
                    projects=[
                        DeliveryProject(
                            project=project_ref(pid, projects),  # type: ignore[arg-type]
                            members=people,
                        )
                        for pid, people in by_project.items()
                        if pid is not None
                    ],
                )
            )
        return OrgChart(
            executives=[member(e) for e in current if e.is_executive],
            departments=departments,
            unplaced=[
                member(e) for e in current if not e.is_executive and org.department_of(e) is None
            ],
            delivery=delivery,
        )

    # ------------------------------------------------------------ role authority

    def _check_role_editable(self, actor: Actor, role: Role) -> None:
        if role.key == SUPER_ADMIN:
            raise Forbidden("The Super Admin role can't be changed.")
        if role.key in actor.roles and not actor.is_super_admin:
            raise Forbidden("You can't change a role you hold.")
        if not within_authority(actor, role):
            raise Forbidden("This role has permissions you don't hold.")

    @staticmethod
    def _grantable(actor: Actor, permissions: list[str]) -> list[str]:
        wanted = sorted(set(permissions))
        if WILDCARD in wanted:
            raise Forbidden("Full access can't be granted from role settings.")
        unknown = [p for p in wanted if p not in CATALOGUE]
        if unknown:
            raise ValidationFailed(
                f"Unknown permission '{unknown[0]}'.", details={"unknown": unknown}
            )
        beyond = [p for p in wanted if not actor.can(p)]
        if beyond:
            raise Forbidden(f"You can't grant '{beyond[0]}': you don't hold it yourself.")
        return wanted

    def _role_out(self, actor: Actor, role: Role, members: int) -> RoleOut:
        try:
            self._check_role_editable(actor, role)
            editable = actor.can(ORG_ROLES_MANAGE)
        except Forbidden:
            editable = False
        return RoleOut(
            key=role.key,
            name=role.name,
            description=role.description,
            permissions=sorted(role.permissions),
            is_system=role.is_system,
            member_count=members,
            editable=editable,
            assignable=actor.can(ORG_ROLES_ASSIGN) and within_authority(actor, role),
        )
