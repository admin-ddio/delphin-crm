"""People core: employees, departments and designations.

Rules (HR and Organization Structure briefs; TODO(pilot-port): confirm against the pilot):
- `org.directory.view` sees the directory (name, code, designation, department,
  manager, status, official e-mail); exited people only with `include_exited`;
- employment details (type, arrangement, dates, reporting relationships, history) are
  visible to the employee, their direct chain, anyone holding a reporting relationship
  over them (explicit or inherited from the department), and `hr.view_all`;
- personal information is visible to the employee and `hr.personal.view` only; the
  employee may edit their own personal details;
- `hr.manage` creates employees and edits their records (EDIT_EMPLOYEE_PROFILE);
- placement (department, designation, executive flag, direct manager) needs
  `org.reporting.manage`; departments `org.departments.manage`; designations
  `org.designations.manage`. A designation never grants CRM permissions;
- one direct manager at a time (history kept) and no reporting loops, counting
  direct and functional (including inherited) lines;
- an employee links to at most one existing sign-in account (never duplicated);
- exits go through offboarding (a later phase), not a status edit;
- every change is audited; employment changes also go to the employee's history.
"""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import date
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.actor import Actor
from app.authz.permissions import (
    HR_MANAGE,
    HR_PERSONAL_VIEW,
    HR_VIEW_ALL,
    ORG_DEPARTMENTS_MANAGE,
    ORG_DESIGNATIONS_MANAGE,
    ORG_DIRECTORY_VIEW,
    ORG_PROJECTS_ASSIGN,
    ORG_REPORTING_MANAGE,
    PROJECTS_VIEW_ALL,
)
from app.core.clock import Clock, business_today
from app.core.errors import (
    BusinessRuleViolation,
    Conflict,
    Forbidden,
    NotFound,
    ValidationFailed,
)
from app.modules.team.models import (
    Department,
    Designation,
    Employee,
    EmployeePersonal,
    EmploymentEvent,
    ReportingLine,
)
from app.modules.team.repository import PeopleRepository
from app.modules.team.schemas import (
    DepartmentIn,
    DepartmentOut,
    DepartmentUpdate,
    DesignationIn,
    DesignationOut,
    DesignationUpdate,
    EmployeeCreate,
    EmployeeDetail,
    EmployeeListItem,
    EmployeePermissions,
    EmployeeUpdate,
    Employment,
    EmploymentEventOut,
    Personal,
    PersonalUpdate,
    PersonRef,
    ProjectRef,
    Ref,
    UserOption,
)
from app.modules.team.service.structure import Org
from app.platform.audit.service import AuditWriter
from app.platform.system.counters import format_code, next_value

STATUS_LABELS: dict[str, str] = {
    "onboarding": "Onboarding",
    "probation": "On probation",
    "active": "Active",
    "notice": "Notice period",
    "on_hold": "On hold",
    "exited": "Exited",
}
TYPE_LABELS: dict[str, str] = {
    "full_time": "Full-time",
    "part_time": "Part-time",
    "intern": "Intern",
    "contractor": "Contractor",
    "consultant": "Consultant",
}
ARRANGEMENT_LABELS: dict[str, str] = {"remote": "Remote", "hybrid": "Hybrid", "office": "Office"}
PERSONAL_FIELDS = (
    "personal_email",
    "phone",
    "date_of_birth",
    "current_address",
    "permanent_address",
    "emergency_name",
    "emergency_relationship",
    "emergency_phone",
)
#: Employee fields that are organisation placement, not the HR record.
PLACEMENT_FIELDS = frozenset({"department_id", "designation_id", "is_executive", "manager_id"})
EMPLOYEE_NOT_FOUND = "This employee doesn't exist."
_UNSET = object()


def _s(value: object) -> object:
    if isinstance(value, uuid.UUID | date):
        return str(value)
    return value


async def load_org(repo: PeopleRepository) -> Org:
    owners: dict[uuid.UUID, list[uuid.UUID]] = {}
    for owner in await repo.owners():
        owners.setdefault(owner.department_id, []).append(owner.employee_id)
    return Org(
        employees={e.id: e for e in await repo.employees()},
        departments={d.id: d for d in await repo.departments()},
        designations={d.id: d for d in await repo.designations()},
        lines=await repo.open_lines(),
        owners=owners,
    )


async def visible_projects(repo: PeopleRepository, actor: Actor) -> dict[uuid.UUID, ProjectRef]:
    """Projects whose name the actor may see next to a Project Manager assignment."""
    see_all = actor.can_any(PROJECTS_VIEW_ALL, ORG_PROJECTS_ASSIGN, ORG_REPORTING_MANAGE)
    return {
        p.id: ProjectRef(id=p.id, code=p.code, name=p.name)
        for p in await repo.projects()
        if see_all or p.manager_id == actor.user_id
    }


def require(actor: Actor, permission: str, message: str) -> None:
    if not actor.can(permission):
        raise Forbidden(message)


def require_active(org: Org, employee_id: uuid.UUID, role: str) -> Employee:
    employee = org.employees.get(employee_id)
    if employee is None or employee.status == "exited":
        raise ValidationFailed(f"Choose a current employee as {role}.")
    return employee


class PeopleService:
    def __init__(self, session: AsyncSession, *, clock: Clock) -> None:
        self._session = session
        self._repo = PeopleRepository(session)
        self._clock = clock
        self._audit = AuditWriter(session)

    # ================================================================ reads

    async def list_employees(
        self,
        actor: Actor,
        *,
        q: str | None = None,
        department_id: uuid.UUID | None = None,
        designation_id: uuid.UUID | None = None,
        status: str | None = None,
        include_exited: bool = False,
    ) -> list[EmployeeListItem]:
        require(actor, ORG_DIRECTORY_VIEW, "You can't see the employee directory.")
        org = await self._org()
        needle = (q or "").strip().lower()
        items = []
        for employee in org.employees.values():
            if employee.status == "exited" and not include_exited and status != "exited":
                continue
            if department_id and employee.department_id != department_id:
                continue
            if designation_id and employee.designation_id != designation_id:
                continue
            if status and employee.status != status:
                continue
            haystack = (
                employee.full_name,
                employee.preferred_name,
                employee.code,
                employee.official_email,
            )
            if needle and not any(needle in (value or "").lower() for value in haystack):
                continue
            items.append(self._item(actor, org, employee))
        return items

    async def get(self, actor: Actor, employee_id: uuid.UUID) -> EmployeeDetail:
        org = await self._org()
        employee = self._find(org, employee_id)
        if employee.user_id != actor.user_id:
            require(actor, ORG_DIRECTORY_VIEW, "You can't see the employee directory.")
        return await self._detail(actor, org, employee)

    async def history(self, actor: Actor, employee_id: uuid.UUID) -> list[EmploymentEventOut]:
        org = await self._org()
        employee = self._find(org, employee_id)
        if not self._sees_employment(actor, org, employee):
            raise Forbidden("You can't see this employee's employment history.")
        return [
            EmploymentEventOut(
                id=event.id,
                kind=event.kind,
                summary=event.summary,
                effective_on=event.effective_on,
                occurred_at=event.occurred_at,
                actor=user.full_name if user else None,
                changes=event.changes,
            )
            for event, user in await self._repo.events(employee.id)
        ]

    async def user_options(self, actor: Actor) -> list[UserOption]:
        self._require_hr(actor)
        return [
            UserOption(id=u.id, full_name=u.full_name, email=u.email)
            for u in await self._repo.unlinked_users()
        ]

    # ================================================================ employees

    async def create(self, actor: Actor, data: EmployeeCreate) -> EmployeeDetail:
        self._require_hr(actor)
        if data.department_id or data.designation_id or data.manager_id:
            self._require_placement(actor)
        org = await self._org()
        email = str(data.official_email) if data.official_email else None
        await self._unique_email(email)
        await self._check_department(data.department_id)
        await self._check_designation(data.designation_id)
        if data.user_id:
            await self._check_user(data.user_id)
        manager = require_active(org, data.manager_id, "manager") if data.manager_id else None

        employee = Employee(
            code=format_code("DD", await next_value(self._session, "employee")),
            user_id=data.user_id,
            full_name=data.full_name,
            preferred_name=data.preferred_name,
            official_email=email,
            department_id=data.department_id,
            designation_id=data.designation_id,
            employment_type=data.employment_type,
            work_arrangement=data.work_arrangement,
            status=data.status,
            joining_date=data.joining_date,
            created_by_id=actor.user_id,
        )
        self._repo.add(employee)
        await self._flush_unique()
        self._repo.add(EmployeePersonal(employee_id=employee.id))
        if manager:
            self._repo.add(
                ReportingLine(
                    employee_id=employee.id,
                    manager_id=manager.id,
                    kind="direct_manager",
                    starts_on=self._today(),
                    created_by_id=actor.user_id,
                )
            )
        parts = [
            org.designations[data.designation_id].name if data.designation_id else None,
            org.departments[data.department_id].name if data.department_id else None,
            f"reports to {manager.full_name}" if manager else None,
        ]
        detail = ", ".join(p for p in parts if p)
        self._event(
            actor,
            employee,
            "created",
            "Employee record created" + (f": {detail}" if detail else ""),
            effective_on=data.joining_date,
        )
        await self._audit.record(
            action="employee.created",
            entity_type="employee",
            entity_id=employee.id,
            actor_user_id=actor.user_id,
            changes={
                "full_name": employee.full_name,
                "department_id": _s(employee.department_id),
                "designation_id": _s(employee.designation_id),
                "manager_id": _s(manager.id if manager else None),
                "user_id": _s(employee.user_id),
            },
            context={"code": employee.code},
        )
        await self._repo.flush()
        return await self.get(actor, employee.id)

    async def update(  # noqa: PLR0912  # HR fields, placement and manager in one edit
        self, actor: Actor, employee_id: uuid.UUID, data: EmployeeUpdate
    ) -> EmployeeDetail:
        incoming = data.model_dump(exclude_unset=True)
        if set(incoming) & PLACEMENT_FIELDS:
            self._require_placement(actor)
        if set(incoming) - PLACEMENT_FIELDS:
            self._require_hr(actor)
        if not incoming:
            self._require_hr(actor)
        org = await self._org()
        employee = self._find(org, employee_id)
        await self._validate_update(org, employee, incoming)
        new_manager = incoming.pop("manager_id", _UNSET)
        today = self._today()

        record: dict[str, Any] = {}
        placement: dict[str, Any] = {}
        summaries: list[tuple[str, str]] = []
        for name, new in incoming.items():
            old = getattr(employee, name)
            if old == new:
                continue
            (placement if name in PLACEMENT_FIELDS else record)[name] = [_s(old), _s(new)]
            summaries.append(self._change_summary(org, name, old, new))
        current = org.manager_of.get(employee.id)
        manager_changes = new_manager is not _UNSET and new_manager != current
        target = new_manager if isinstance(new_manager, uuid.UUID) else None

        # Loops are checked on the organisation as it would be after the change.
        if manager_changes or "department_id" in placement:
            after = org
            if "department_id" in placement:
                after = after.with_move(employee.id, incoming["department_id"])
            if manager_changes:
                after = after.with_lines(
                    employee.id,
                    [ln for ln in org.by_employee[employee.id] if ln.kind != "direct_manager"]
                    + (
                        [
                            ReportingLine(
                                employee_id=employee.id, manager_id=target, kind="direct_manager"
                            )
                        ]
                        if target
                        else []
                    ),
                )
            loop = after.loop_through(employee.id)
            if loop:
                raise BusinessRuleViolation(after.loop_message(loop))

        for name, new in incoming.items():
            setattr(employee, name, new)
        if manager_changes:
            await self._set_manager(actor, org, employee, target, today)
            placement["manager_id"] = [_s(current), _s(target)]
            summaries.append(
                ("manager_changed", f"Reporting manager: {org.name(current)} → {org.name(target)}")
            )
        if not (record or placement):
            return await self._detail(actor, org, employee)

        await self._flush_unique()
        for kind, summary in summaries:
            self._event(actor, employee, kind, summary, effective_on=today)
        for action, changes in (
            ("employee.updated", record),
            ("employee.placement_changed", placement),
        ):
            if changes:
                await self._audit.record(
                    action=action,
                    entity_type="employee",
                    entity_id=employee.id,
                    actor_user_id=actor.user_id,
                    changes=changes,
                    context={"code": employee.code, "name": employee.full_name},
                )
        await self._repo.flush()
        return await self.get(actor, employee.id)

    async def update_personal(
        self, actor: Actor, employee_id: uuid.UUID, data: PersonalUpdate
    ) -> EmployeeDetail:
        org = await self._org()
        employee = self._find(org, employee_id)
        if not (employee.user_id == actor.user_id or actor.can(HR_MANAGE)):
            raise Forbidden("Only the employee or HR can change personal details.")
        personal = await self._repo.personal(employee.id)
        if personal is None:
            personal = EmployeePersonal(employee_id=employee.id)
            self._repo.add(personal)
        incoming = data.model_dump(exclude_unset=True)
        if incoming.get("personal_email") is not None:
            incoming["personal_email"] = str(incoming["personal_email"])
        changed: list[str] = []
        for name, new in incoming.items():
            target: Employee | EmployeePersonal = employee if name == "preferred_name" else personal
            if getattr(target, name) != new:
                setattr(target, name, new)
                changed.append(name)
        if changed:
            # Values are personal: the audit and history record which fields changed only.
            await self._audit.record(
                action="employee.personal_updated",
                entity_type="employee",
                entity_id=employee.id,
                actor_user_id=actor.user_id,
                changes={"fields": changed},
                context={"code": employee.code},
            )
            self._event(
                actor,
                employee,
                "personal_updated",
                "Personal details updated: " + ", ".join(f.replace("_", " ") for f in changed),
            )
            await self._repo.flush()
        return await self.get(actor, employee.id)

    # ================================================================ departments

    async def departments(self) -> list[DepartmentOut]:
        org = await self._org()
        counts = Counter(e.department_id for e in org.employees.values() if e.status != "exited")
        return [self._department_out(org, d, counts[d.id]) for d in org.departments.values()]

    async def create_department(self, actor: Actor, data: DepartmentIn) -> DepartmentOut:
        require(actor, ORG_DEPARTMENTS_MANAGE, "You can't manage departments.")
        if await self._repo.department_by_name(data.name):
            raise Conflict(f"A department called {data.name} already exists.")
        org = await self._org()
        head = require_active(org, data.head_id, "department head") if data.head_id else None
        delivery = (
            require_active(org, data.delivery_manager_id, "delivery manager")
            if data.delivery_manager_id
            else None
        )
        owners = self._owner_ids(org, data.owner_ids)
        department = Department(
            name=data.name,
            description=data.description,
            head_id=head.id if head else None,
            delivery_manager_id=delivery.id if delivery else None,
        )
        self._repo.add(department)
        await self._repo.flush()
        if owners:
            await self._repo.replace_owners(department.id, owners, actor.user_id)
        await self._audit.record(
            action="department.created",
            entity_type="department",
            entity_id=department.id,
            actor_user_id=actor.user_id,
            changes={
                "name": data.name,
                "head_id": _s(department.head_id),
                "delivery_manager_id": _s(department.delivery_manager_id),
                "owner_ids": [str(i) for i in owners],
            },
            context={"name": data.name},
        )
        return self._department_out(org.with_owners(department.id, owners), department, 0)

    async def update_department(  # noqa: PLR0912  # one guard per field
        self, actor: Actor, department_id: uuid.UUID, data: DepartmentUpdate
    ) -> DepartmentOut:
        require(actor, ORG_DEPARTMENTS_MANAGE, "You can't manage departments.")
        org = await self._org()
        department = org.departments.get(department_id)
        if department is None:
            raise NotFound("This department doesn't exist.")
        incoming = data.model_dump(exclude_unset=True)
        if "name" in incoming:
            if not incoming["name"]:
                raise ValidationFailed("The department name can't be empty.")
            same = await self._repo.department_by_name(incoming["name"])
            if same is not None and same.id != department.id:
                raise Conflict(f"A department called {incoming['name']} already exists.")
        if incoming.get("head_id"):
            require_active(org, incoming["head_id"], "department head")
        if incoming.get("delivery_manager_id"):
            require_active(org, incoming["delivery_manager_id"], "delivery manager")
        for optional in ("is_active", "owner_ids"):
            if optional in incoming and incoming[optional] is None:
                del incoming[optional]
        headcount = sum(
            1
            for e in org.employees.values()
            if e.department_id == department.id and e.status != "exited"
        )
        if incoming.get("is_active") is False and headcount:
            raise BusinessRuleViolation(
                f"Move the department's {headcount} employee(s) before deactivating it."
            )
        changes: dict[str, Any] = {}
        new_owners = incoming.pop("owner_ids", None)
        if new_owners is not None:
            owners = self._owner_ids(org, new_owners)
            old_owners = org.owners.get(department.id, [])
            if owners != old_owners:
                after = org.with_owners(department.id, owners)
                members = [e.id for e in org.employees.values() if e.department_id == department.id]
                loop = after.first_loop(members)
                if loop:
                    raise BusinessRuleViolation(after.loop_message(loop))
                await self._repo.replace_owners(department.id, owners, actor.user_id)
                changes["owner_ids"] = [[str(i) for i in old_owners], [str(i) for i in owners]]
                org = after
        for name, new in incoming.items():
            old = getattr(department, name)
            if old != new:
                changes[name] = [_s(old), _s(new)]
                setattr(department, name, new)
        if changes:
            await self._repo.flush()
            await self._audit.record(
                action="department.updated",
                entity_type="department",
                entity_id=department.id,
                actor_user_id=actor.user_id,
                changes=changes,
                context={"name": department.name},
            )
        return self._department_out(org, department, headcount)

    # ================================================================ designations

    async def designations(self) -> list[DesignationOut]:
        org = await self._org()
        counts = Counter(e.designation_id for e in org.employees.values() if e.status != "exited")
        return [self._designation_out(org, d, counts[d.id]) for d in org.designations.values()]

    async def create_designation(self, actor: Actor, data: DesignationIn) -> DesignationOut:
        require(actor, ORG_DESIGNATIONS_MANAGE, "You can't manage designations.")
        await self._check_department(data.department_id)
        if await self._repo.designation_by_name(data.name, data.department_id):
            raise Conflict(f"The designation {data.name} already exists in that department.")
        designation = Designation(name=data.name, department_id=data.department_id)
        self._repo.add(designation)
        await self._repo.flush()
        await self._audit.record(
            action="designation.created",
            entity_type="designation",
            entity_id=designation.id,
            actor_user_id=actor.user_id,
            changes={"name": data.name, "department_id": _s(data.department_id)},
            context={"name": data.name},
        )
        org = await self._org()
        return self._designation_out(org, designation, 0)

    async def update_designation(
        self, actor: Actor, designation_id: uuid.UUID, data: DesignationUpdate
    ) -> DesignationOut:
        require(actor, ORG_DESIGNATIONS_MANAGE, "You can't manage designations.")
        designation = await self._repo.designation(designation_id)
        if designation is None:
            raise NotFound("This designation doesn't exist.")
        incoming = data.model_dump(exclude_unset=True)
        if "is_active" in incoming and incoming["is_active"] is None:
            del incoming["is_active"]
        if "name" in incoming and not incoming["name"]:
            raise ValidationFailed("The designation can't be empty.")
        if incoming.get("department_id"):
            await self._check_department(incoming["department_id"])
        name = incoming.get("name", designation.name)
        department_id = incoming.get("department_id", designation.department_id)
        same = await self._repo.designation_by_name(name, department_id)
        if same is not None and same.id != designation.id:
            raise Conflict(f"The designation {name} already exists in that department.")
        changes = {}
        for field_name, new in incoming.items():
            if getattr(designation, field_name) != new:
                changes[field_name] = [_s(getattr(designation, field_name)), _s(new)]
                setattr(designation, field_name, new)
        if changes:
            await self._repo.flush()
            await self._audit.record(
                action="designation.updated",
                entity_type="designation",
                entity_id=designation.id,
                actor_user_id=actor.user_id,
                changes=changes,
                context={"name": designation.name},
            )
        return next(d for d in await self.designations() if d.id == designation.id)

    # ================================================================ helpers

    def _today(self) -> date:
        return business_today(self._clock)

    async def _org(self) -> Org:
        return await load_org(self._repo)

    @staticmethod
    def _find(org: Org, employee_id: uuid.UUID) -> Employee:
        employee = org.employees.get(employee_id)
        if employee is None:
            raise NotFound(EMPLOYEE_NOT_FOUND)
        return employee

    @staticmethod
    def _require_hr(actor: Actor) -> None:
        require(actor, HR_MANAGE, "Only HR can change employee records.")

    @staticmethod
    def _require_placement(actor: Actor) -> None:
        require(
            actor,
            ORG_REPORTING_MANAGE,
            "Departments, designations and reporting lines are changed in "
            "Organization & Role Settings.",
        )

    @staticmethod
    def _owner_ids(org: Org, ids: list[uuid.UUID]) -> list[uuid.UUID]:
        unique = list(dict.fromkeys(ids))
        for owner_id in unique:
            require_active(org, owner_id, "executive owner")
        return unique

    @staticmethod
    def _sees_employment(actor: Actor, org: Org, employee: Employee) -> bool:
        if employee.user_id == actor.user_id or actor.can(HR_VIEW_ALL):
            return True
        me = org.by_user(actor.user_id)
        return me is not None and org.above(me.id, employee)

    async def _validate_update(
        self, org: Org, employee: Employee, incoming: dict[str, Any]
    ) -> None:
        if "full_name" in incoming and not incoming["full_name"]:
            raise ValidationFailed("The employee's name can't be empty.")
        for required in ("employment_type", "status", "is_executive"):
            if required in incoming and incoming[required] is None:
                raise ValidationFailed(f"{required.replace('_', ' ').capitalize()} is required.")
        if incoming.get("status") == "exited" and employee.status != "exited":
            raise BusinessRuleViolation(
                "Exits go through offboarding, which arrives in a later phase."
            )
        if incoming.get("official_email") is not None:
            incoming["official_email"] = str(incoming["official_email"])
            await self._unique_email(incoming["official_email"], exclude=employee.id)
        if incoming.get("department_id"):
            await self._check_department(incoming["department_id"])
        if incoming.get("designation_id"):
            await self._check_designation(incoming["designation_id"])
        if incoming.get("user_id") and incoming["user_id"] != employee.user_id:
            await self._check_user(incoming["user_id"])
        manager_id = incoming.get("manager_id")
        if manager_id is not None:
            if manager_id == employee.id:
                raise ValidationFailed("An employee can't report to themselves.")
            require_active(org, manager_id, "manager")

    async def _unique_email(self, email: str | None, *, exclude: uuid.UUID | None = None) -> None:
        if email and await self._repo.by_official_email(email, exclude=exclude):
            raise Conflict(f"Another employee already uses {email}.")

    async def _check_department(self, department_id: uuid.UUID | None) -> None:
        if department_id is None:
            return
        department = await self._repo.department(department_id)
        if department is None or not department.is_active:
            raise ValidationFailed("Choose an active department.")

    async def _check_designation(self, designation_id: uuid.UUID | None) -> None:
        if designation_id is None:
            return
        designation = await self._repo.designation(designation_id)
        if designation is None or not designation.is_active:
            raise ValidationFailed("Choose an active designation.")

    async def _check_user(self, user_id: uuid.UUID) -> None:
        user = await self._repo.user(user_id)
        if user is None or not user.is_active or user.approved_at is None:
            raise ValidationFailed("Choose an active, approved sign-in account.")
        if await self._repo.employee_for_user(user_id):
            raise Conflict("That account is already linked to another employee.")

    async def _flush_unique(self) -> None:
        try:
            await self._repo.flush()
        except IntegrityError as exc:  # lost a race on a unique e-mail / account link
            raise Conflict("Another employee already uses that e-mail or account.") from exc

    async def _set_manager(
        self,
        actor: Actor,
        org: Org,
        employee: Employee,
        manager_id: uuid.UUID | None,
        today: date,
    ) -> None:
        current = next(iter(org.explicit(employee.id, "direct_manager")), None)
        if current is not None:
            current.ends_on = max(today, current.starts_on)
            current.ended_by_id = actor.user_id
            await self._repo.flush()
        if manager_id is not None:
            self._repo.add(
                ReportingLine(
                    employee_id=employee.id,
                    manager_id=manager_id,
                    kind="direct_manager",
                    starts_on=today,
                    created_by_id=actor.user_id,
                )
            )

    @staticmethod
    def _change_summary(org: Org, name: str, old: object, new: object) -> tuple[str, str]:
        def label(value: object) -> str:
            if value is None:
                return "—"
            if isinstance(value, bool):
                return "Yes" if value else "No"
            if isinstance(value, uuid.UUID):
                if name == "department_id":
                    return org.departments[value].name
                if name == "designation_id":
                    return org.designations[value].name
                return org.name(value)
            mapping = {
                "status": STATUS_LABELS,
                "employment_type": TYPE_LABELS,
                "work_arrangement": ARRANGEMENT_LABELS,
            }.get(name)
            return mapping.get(str(value), str(value)) if mapping else str(value)

        if name == "user_id":
            return "account_linked", "Sign-in account " + ("linked" if new else "unlinked")
        if name == "is_executive":
            return "executive_changed", (
                "Added to executive leadership" if new else "Removed from executive leadership"
            )
        kind = {
            "department_id": "department_changed",
            "designation_id": "designation_changed",
            "status": "status_changed",
        }.get(name, "employment_updated")
        title = name.removesuffix("_id").replace("_", " ").capitalize()
        return kind, f"{title}: {label(old)} → {label(new)}"

    def _event(
        self,
        actor: Actor,
        employee: Employee,
        kind: str,
        summary: str,
        *,
        effective_on: date | None = None,
    ) -> None:
        self._repo.add(
            EmploymentEvent(
                employee_id=employee.id,
                kind=kind,
                summary=summary,
                effective_on=effective_on,
                actor_user_id=actor.user_id,
            )
        )

    @staticmethod
    def _item(actor: Actor, org: Org, employee: Employee) -> EmployeeListItem:
        designation = (
            org.designations.get(employee.designation_id) if employee.designation_id else None
        )
        department = org.department_of(employee)
        return EmployeeListItem(
            id=employee.id,
            code=employee.code,
            full_name=employee.full_name,
            preferred_name=employee.preferred_name,
            official_email=employee.official_email,
            designation=Ref(id=designation.id, name=designation.name) if designation else None,
            department=Ref(id=department.id, name=department.name) if department else None,
            manager=org.person(org.manager_of.get(employee.id)),
            status=employee.status,  # type: ignore[arg-type]  # DB check constraint
            status_label=STATUS_LABELS[employee.status],
            is_executive=employee.is_executive,
            user_id=employee.user_id,
            is_me=employee.user_id is not None and employee.user_id == actor.user_id,
        )

    async def _detail(self, actor: Actor, org: Org, employee: Employee) -> EmployeeDetail:
        item = self._item(actor, org, employee)
        employment = None
        if self._sees_employment(actor, org, employee):
            department = org.department_of(employee)
            projects = (
                await visible_projects(self._repo, actor)
                if org.explicit(employee.id, "project_manager")
                else {}
            )
            approver = next(iter(org.resolve_kind(employee, "leave_approver")), None)
            employment = Employment(
                employment_type=employee.employment_type,  # type: ignore[arg-type]
                work_arrangement=employee.work_arrangement,  # type: ignore[arg-type]
                joining_date=employee.joining_date,
                reporting=org.relations(employee, projects),
                effective_leave_approver=org.person(approver.manager_id) if approver else None,
                department_head=org.person(department.head_id if department else None),
                has_account=employee.user_id is not None,
            )
        personal = None
        if item.is_me or actor.can(HR_PERSONAL_VIEW):
            row = await self._repo.personal(employee.id)
            personal = Personal(
                **{name: getattr(row, name) if row else None for name in PERSONAL_FIELDS}
            )
        reports = sorted(
            (org.employees[i] for i in org.reports[employee.id]), key=lambda e: e.full_name
        )
        return EmployeeDetail(
            **item.model_dump(),
            created_at=employee.created_at,
            direct_reports=[
                PersonRef(id=e.id, code=e.code, full_name=e.full_name)
                for e in reports
                if e.status != "exited"
            ],
            employment=employment,
            personal=personal,
            permissions=EmployeePermissions(
                manage=actor.can(HR_MANAGE),
                edit_personal=item.is_me or actor.can(HR_MANAGE),
                manage_reporting=actor.can(ORG_REPORTING_MANAGE),
            ),
        )

    @staticmethod
    def _department_out(org: Org, department: Department, headcount: int) -> DepartmentOut:
        return DepartmentOut(
            id=department.id,
            name=department.name,
            description=department.description,
            head=org.person(department.head_id),
            owners=org.people(org.owners.get(department.id, [])),
            delivery_manager=org.person(department.delivery_manager_id),
            headcount=headcount,
            is_active=department.is_active,
        )

    @staticmethod
    def _designation_out(org: Org, designation: Designation, headcount: int) -> DesignationOut:
        department = (
            org.departments.get(designation.department_id) if designation.department_id else None
        )
        return DesignationOut(
            id=designation.id,
            name=designation.name,
            department=Ref(id=department.id, name=department.name) if department else None,
            is_active=designation.is_active,
            headcount=headcount,
        )
