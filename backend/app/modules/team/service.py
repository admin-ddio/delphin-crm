"""Team & Employees: approving self sign-ups, and the people core (employees,
departments, designations, reporting lines; rules above PeopleService).

Sign-up approval rules:
- only actors with `users.approve` see or decide pending sign-ups (router guard);
- approving assigns exactly one existing role and records who approved and when;
- rejecting deletes the pending app user AND its Firebase account, so the e-mail
  can register again later; both decisions are audited.
"""

from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.actor import Actor
from app.authz.permissions import HR_MANAGE, HR_PERSONAL_VIEW, HR_VIEW_ALL
from app.core.clock import Clock
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
from app.modules.team.repository import PeopleRepository, TeamRepository
from app.modules.team.schemas import (
    DepartmentIn,
    DepartmentOut,
    DepartmentUpdate,
    DesignationIn,
    DesignationOut,
    DesignationUpdate,
    DottedLine,
    DottedLineIn,
    EmployeeCreate,
    EmployeeDetail,
    EmployeeListItem,
    EmployeePermissions,
    EmployeeUpdate,
    Employment,
    EmploymentEventOut,
    PendingRegistration,
    Personal,
    PersonalUpdate,
    PersonRef,
    Ref,
    UserOption,
)
from app.platform.audit.service import AuditWriter
from app.platform.identity.firebase import IdentityProvider
from app.platform.identity.models import User
from app.platform.system.counters import format_code, next_value


class TeamService:
    def __init__(self, session: AsyncSession, *, clock: Clock, identity: IdentityProvider) -> None:
        self._repo = TeamRepository(session)
        self._clock = clock
        self._identity = identity
        self._audit = AuditWriter(session)

    async def pending_registrations(self) -> list[PendingRegistration]:
        result = []
        for user in await self._repo.pending_registrations():
            verified = (
                await self._identity.email_verified(user.firebase_uid)
                if user.firebase_uid
                else None
            )
            result.append(
                PendingRegistration(
                    id=user.id,
                    email=user.email,
                    full_name=user.full_name,
                    registered_at=user.created_at,
                    email_verified=verified,
                )
            )
        return result

    async def approve(self, actor: Actor, user_id: uuid.UUID, role_key: str) -> None:
        user = await self._pending(user_id)
        role = await self._repo.role_by_key(role_key)
        if role is None:
            raise ValidationFailed(f"Unknown role '{role_key}'.", details={"role": role_key})
        user.approved_at = self._clock.now()
        user.approved_by_id = actor.user_id
        self._repo.add_role(user.id, role.id, actor.user_id)
        await self._audit.record(
            action="team.registration_approved",
            entity_type="user",
            entity_id=user.id,
            actor_user_id=actor.user_id,
            context={"role": role_key, "email": user.email},
        )

    async def reject(self, actor: Actor, user_id: uuid.UUID) -> None:
        user = await self._pending(user_id)
        email, uid = user.email, user.firebase_uid
        await self._repo.delete(user)
        if uid:
            await self._identity.delete_user(uid)
        await self._audit.record(
            action="team.registration_rejected",
            entity_type="user",
            entity_id=user_id,
            actor_user_id=actor.user_id,
            context={"email": email},
        )

    async def _pending(self, user_id: uuid.UUID) -> User:
        user = await self._repo.pending_registration(user_id)
        if user is None:
            raise NotFound("This sign-up was not found or has already been handled.")
        return user


# ==================================================================== people core
#
# Rules (from the HR brief; TODO(pilot-port): confirm against the pilot):
# - everyone signed in sees the directory (name, code, designation, department,
#   manager, status, official e-mail); exited people only with `include_exited`;
# - employment details (type, arrangement, dates, approvers, dotted lines, history)
#   are visible to the employee, anyone above them in the reporting chain, a dotted-
#   line manager, their department head, and `hr.view_all`;
# - personal information is visible to the employee and `hr.personal.view` only;
#   the employee may edit their own personal details;
# - `hr.manage` creates employees and changes employment, departments, designations
#   and reporting lines; one direct manager at a time (history kept), no loops,
#   any number of dotted lines;
# - an employee links to at most one existing sign-in account (never duplicated);
# - exits go through offboarding (a later phase), not a status edit;
# - every change is audited; employment changes also go to the employee's history.

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
EMPLOYEE_NOT_FOUND = "This employee doesn't exist."
_UNSET = object()


@dataclass
class Org:
    """The whole organisation in memory (small agency: a few hundred rows at most)."""

    employees: dict[uuid.UUID, Employee]
    departments: dict[uuid.UUID, Department]
    designations: dict[uuid.UUID, Designation]
    lines: list[ReportingLine]
    manager_of: dict[uuid.UUID, uuid.UUID] = field(default_factory=dict)
    dotted: dict[uuid.UUID, list[ReportingLine]] = field(default_factory=lambda: defaultdict(list))
    reports: dict[uuid.UUID, list[uuid.UUID]] = field(default_factory=lambda: defaultdict(list))

    def __post_init__(self) -> None:
        for line in self.lines:
            if line.kind == "direct":
                self.manager_of[line.employee_id] = line.manager_id
                self.reports[line.manager_id].append(line.employee_id)
            else:
                self.dotted[line.employee_id].append(line)

    def by_user(self, user_id: uuid.UUID) -> Employee | None:
        return next((e for e in self.employees.values() if e.user_id == user_id), None)

    def chain(self, employee_id: uuid.UUID) -> list[uuid.UUID]:
        """Direct managers upward (loop-safe)."""
        seen: list[uuid.UUID] = []
        current = self.manager_of.get(employee_id)
        while current is not None and current not in seen:
            seen.append(current)
            current = self.manager_of.get(current)
        return seen

    def above(self, viewer_id: uuid.UUID, employee: Employee) -> bool:
        """Viewer is in the employee's chain, a dotted-line manager, or department head."""
        if viewer_id in self.chain(employee.id):
            return True
        if any(line.manager_id == viewer_id for line in self.dotted[employee.id]):
            return True
        department = self.department_of(employee)
        return department is not None and department.head_id == viewer_id

    def department_of(self, employee: Employee) -> Department | None:
        return self.departments.get(employee.department_id) if employee.department_id else None

    def person(self, employee_id: uuid.UUID | None) -> PersonRef | None:
        employee = self.employees.get(employee_id) if employee_id else None
        if employee is None:
            return None
        return PersonRef(id=employee.id, code=employee.code, full_name=employee.full_name)

    def name(self, employee_id: uuid.UUID | None) -> str:
        employee = self.employees.get(employee_id) if employee_id else None
        return employee.full_name if employee else "—"


def _s(value: object) -> object:
    if isinstance(value, uuid.UUID | date):
        return str(value)
    return value


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
        status: str | None = None,
        include_exited: bool = False,
    ) -> list[EmployeeListItem]:
        org = await self._org()
        needle = (q or "").strip().lower()
        items = []
        for employee in org.employees.values():
            if employee.status == "exited" and not include_exited and status != "exited":
                continue
            if department_id and employee.department_id != department_id:
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
        return await self._detail(actor, org, self._find(org, employee_id))

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
        self._require_manage(actor)
        return [
            UserOption(id=u.id, full_name=u.full_name, email=u.email)
            for u in await self._repo.unlinked_users()
        ]

    # ================================================================ employees

    async def create(self, actor: Actor, data: EmployeeCreate) -> EmployeeDetail:
        self._require_manage(actor)
        org = await self._org()
        email = str(data.official_email) if data.official_email else None
        await self._unique_email(email)
        await self._check_department(data.department_id)
        await self._check_designation(data.designation_id)
        if data.user_id:
            await self._check_user(data.user_id)
        manager = self._active(org, data.manager_id, "manager") if data.manager_id else None
        approver = (
            self._active(org, data.leave_approver_id, "leave approver")
            if data.leave_approver_id
            else None
        )

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
            leave_approver_id=approver.id if approver else None,
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
                    kind="direct",
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

    async def update(
        self, actor: Actor, employee_id: uuid.UUID, data: EmployeeUpdate
    ) -> EmployeeDetail:
        self._require_manage(actor)
        org = await self._org()
        employee = self._find(org, employee_id)
        incoming = data.model_dump(exclude_unset=True)
        await self._validate_update(org, employee, incoming)
        new_manager = incoming.pop("manager_id", _UNSET)
        today = self._today()

        changes: dict[str, Any] = {}
        summaries: list[tuple[str, str]] = []
        for name, new in incoming.items():
            old = getattr(employee, name)
            if old == new:
                continue
            changes[name] = [_s(old), _s(new)]
            summaries.append(self._change_summary(org, name, old, new))
            setattr(employee, name, new)

        current = org.manager_of.get(employee.id)
        if new_manager is not _UNSET and new_manager != current:
            target = new_manager if isinstance(new_manager, uuid.UUID) else None
            await self._set_manager(actor, org, employee, target, today)
            changes["manager_id"] = [_s(current), _s(target)]
            summaries.append(
                ("manager_changed", f"Reporting manager: {org.name(current)} → {org.name(target)}")
            )
        if not changes:
            return await self._detail(actor, org, employee)

        await self._flush_unique()
        for kind, summary in summaries:
            self._event(actor, employee, kind, summary, effective_on=today)
        await self._audit.record(
            action="employee.updated",
            entity_type="employee",
            entity_id=employee.id,
            actor_user_id=actor.user_id,
            changes=changes,
            context={"code": employee.code},
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

    async def add_dotted_line(
        self, actor: Actor, employee_id: uuid.UUID, data: DottedLineIn
    ) -> EmployeeDetail:
        self._require_manage(actor)
        org = await self._org()
        employee = self._find(org, employee_id)
        if data.manager_id == employee.id:
            raise ValidationFailed("An employee can't report to themselves.")
        manager = self._active(org, data.manager_id, "manager")
        if any(line.manager_id == manager.id for line in org.dotted[employee.id]):
            raise Conflict(
                f"{employee.full_name} already has a dotted line to {manager.full_name}."
            )
        if org.manager_of.get(employee.id) == manager.id:
            raise Conflict(f"{manager.full_name} is already the direct manager.")
        self._repo.add(
            ReportingLine(
                employee_id=employee.id,
                manager_id=manager.id,
                kind="dotted",
                starts_on=self._today(),
                created_by_id=actor.user_id,
            )
        )
        self._event(
            actor,
            employee,
            "dotted_line_added",
            f"Dotted-line reporting to {manager.full_name} added",
            effective_on=self._today(),
        )
        await self._audit.record(
            action="employee.dotted_line_added",
            entity_type="employee",
            entity_id=employee.id,
            actor_user_id=actor.user_id,
            changes={"manager_id": str(manager.id)},
        )
        await self._repo.flush()
        return await self.get(actor, employee.id)

    async def end_dotted_line(
        self, actor: Actor, employee_id: uuid.UUID, line_id: uuid.UUID
    ) -> EmployeeDetail:
        self._require_manage(actor)
        org = await self._org()
        employee = self._find(org, employee_id)
        line = next((ln for ln in org.dotted[employee.id] if ln.id == line_id), None)
        if line is None:
            raise NotFound("This dotted line doesn't exist.")
        line.ends_on = self._today()
        self._event(
            actor,
            employee,
            "dotted_line_ended",
            f"Dotted-line reporting to {org.name(line.manager_id)} ended",
            effective_on=self._today(),
        )
        await self._audit.record(
            action="employee.dotted_line_ended",
            entity_type="employee",
            entity_id=employee.id,
            actor_user_id=actor.user_id,
            changes={"manager_id": str(line.manager_id)},
        )
        await self._repo.flush()
        return await self.get(actor, employee.id)

    # ================================================================ departments, designations

    async def departments(self) -> list[DepartmentOut]:
        org = await self._org()
        counts = Counter(e.department_id for e in org.employees.values() if e.status != "exited")
        return [self._department_out(org, d, counts[d.id]) for d in org.departments.values()]

    async def create_department(self, actor: Actor, data: DepartmentIn) -> DepartmentOut:
        self._require_manage(actor)
        if await self._repo.department_by_name(data.name):
            raise Conflict(f"A department called {data.name} already exists.")
        org = await self._org()
        head = self._active(org, data.head_id, "department head") if data.head_id else None
        department = Department(
            name=data.name, description=data.description, head_id=head.id if head else None
        )
        self._repo.add(department)
        await self._repo.flush()
        await self._audit.record(
            action="department.created",
            entity_type="department",
            entity_id=department.id,
            actor_user_id=actor.user_id,
            changes={"name": data.name, "head_id": _s(department.head_id)},
        )
        return self._department_out(org, department, 0)

    async def update_department(
        self, actor: Actor, department_id: uuid.UUID, data: DepartmentUpdate
    ) -> DepartmentOut:
        self._require_manage(actor)
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
            self._active(org, incoming["head_id"], "department head")
        if "is_active" in incoming and incoming["is_active"] is None:
            del incoming["is_active"]
        headcount = sum(
            1
            for e in org.employees.values()
            if e.department_id == department.id and e.status != "exited"
        )
        if incoming.get("is_active") is False and headcount:
            raise BusinessRuleViolation(
                f"Move the department's {headcount} employee(s) before deactivating it."
            )
        changes = {}
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
            )
        return self._department_out(org, department, headcount)

    async def designations(self) -> list[DesignationOut]:
        org = await self._org()
        counts = Counter(e.designation_id for e in org.employees.values() if e.status != "exited")
        return [
            DesignationOut(id=d.id, name=d.name, is_active=d.is_active, headcount=counts[d.id])
            for d in org.designations.values()
        ]

    async def create_designation(self, actor: Actor, data: DesignationIn) -> DesignationOut:
        self._require_manage(actor)
        if await self._repo.designation_by_name(data.name):
            raise Conflict(f"The designation {data.name} already exists.")
        designation = Designation(name=data.name)
        self._repo.add(designation)
        await self._repo.flush()
        await self._audit.record(
            action="designation.created",
            entity_type="designation",
            entity_id=designation.id,
            actor_user_id=actor.user_id,
            changes={"name": data.name},
        )
        return DesignationOut(id=designation.id, name=designation.name, is_active=True, headcount=0)

    async def update_designation(
        self, actor: Actor, designation_id: uuid.UUID, data: DesignationUpdate
    ) -> DesignationOut:
        self._require_manage(actor)
        designation = await self._repo.designation(designation_id)
        if designation is None:
            raise NotFound("This designation doesn't exist.")
        incoming = data.model_dump(exclude_unset=True)
        if "name" in incoming:
            if not incoming["name"]:
                raise ValidationFailed("The designation can't be empty.")
            same = await self._repo.designation_by_name(incoming["name"])
            if same is not None and same.id != designation.id:
                raise Conflict(f"The designation {incoming['name']} already exists.")
        changes = {}
        for name, new in incoming.items():
            if new is not None and getattr(designation, name) != new:
                changes[name] = [getattr(designation, name), new]
                setattr(designation, name, new)
        if changes:
            await self._repo.flush()
            await self._audit.record(
                action="designation.updated",
                entity_type="designation",
                entity_id=designation.id,
                actor_user_id=actor.user_id,
                changes=changes,
            )
        return next(d for d in await self.designations() if d.id == designation.id)

    # ================================================================ helpers

    def _today(self) -> date:
        return self._clock.now().date()

    async def _org(self) -> Org:
        return Org(
            employees={e.id: e for e in await self._repo.employees()},
            departments={d.id: d for d in await self._repo.departments()},
            designations={d.id: d for d in await self._repo.designations()},
            lines=await self._repo.open_lines(),
        )

    @staticmethod
    def _find(org: Org, employee_id: uuid.UUID) -> Employee:
        employee = org.employees.get(employee_id)
        if employee is None:
            raise NotFound(EMPLOYEE_NOT_FOUND)
        return employee

    @staticmethod
    def _require_manage(actor: Actor) -> None:
        if not actor.can(HR_MANAGE):
            raise Forbidden("Only HR can change employee records and the organisation.")

    @staticmethod
    def _active(org: Org, employee_id: uuid.UUID, role: str) -> Employee:
        employee = org.employees.get(employee_id)
        if employee is None or employee.status == "exited":
            raise ValidationFailed(f"Choose a current employee as {role}.")
        return employee

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
        for required in ("employment_type", "status"):
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
        if incoming.get("leave_approver_id"):
            if incoming["leave_approver_id"] == employee.id:
                raise ValidationFailed("An employee can't approve their own leave.")
            self._active(org, incoming["leave_approver_id"], "leave approver")

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
        if manager_id is not None:
            if manager_id == employee.id:
                raise ValidationFailed("An employee can't report to themselves.")
            manager = self._active(org, manager_id, "manager")
            if employee.id in org.chain(manager.id):
                raise BusinessRuleViolation(
                    f"That would create a reporting loop: {manager.full_name} already "
                    f"reports to {employee.full_name}."
                )
        current = next(
            (ln for ln in org.lines if ln.employee_id == employee.id and ln.kind == "direct"),
            None,
        )
        if current is not None:
            current.ends_on = today
            await self._repo.flush()
        if manager_id is not None:
            self._repo.add(
                ReportingLine(
                    employee_id=employee.id,
                    manager_id=manager_id,
                    kind="direct",
                    starts_on=today,
                    created_by_id=actor.user_id,
                )
            )

    @staticmethod
    def _change_summary(org: Org, name: str, old: object, new: object) -> tuple[str, str]:
        def label(value: object) -> str:
            if value is None:
                return "—"
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
            user_id=employee.user_id,
            is_me=employee.user_id is not None and employee.user_id == actor.user_id,
        )

    async def _detail(self, actor: Actor, org: Org, employee: Employee) -> EmployeeDetail:
        item = self._item(actor, org, employee)
        employment = None
        if self._sees_employment(actor, org, employee):
            department = org.department_of(employee)
            approver_id = employee.leave_approver_id or org.manager_of.get(employee.id)
            employment = Employment(
                employment_type=employee.employment_type,  # type: ignore[arg-type]
                work_arrangement=employee.work_arrangement,  # type: ignore[arg-type]
                joining_date=employee.joining_date,
                leave_approver=org.person(employee.leave_approver_id),
                effective_leave_approver=org.person(approver_id),
                dotted_lines=[
                    DottedLine(
                        id=line.id,
                        manager=org.person(line.manager_id),  # type: ignore[arg-type]
                        starts_on=line.starts_on,
                    )
                    for line in org.dotted[employee.id]
                ],
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
            ),
        )

    @staticmethod
    def _department_out(org: Org, department: Department, headcount: int) -> DepartmentOut:
        return DepartmentOut(
            id=department.id,
            name=department.name,
            description=department.description,
            head=org.person(department.head_id),
            headcount=headcount,
            is_active=department.is_active,
        )
