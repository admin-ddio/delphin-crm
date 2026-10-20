"""Queries for the team module: sign-up approvals and people core."""

from __future__ import annotations

import uuid

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.projects.models import Project
from app.modules.team.models import (
    Department,
    DepartmentOwner,
    Designation,
    Employee,
    EmployeePersonal,
    EmploymentEvent,
    ReportingLine,
)
from app.platform.audit.models import AuditLog
from app.platform.identity.models import Role, User, UserRole


class TeamRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def pending_registrations(self) -> list[User]:
        rows = await self._session.execute(
            select(User)
            .where(User.approved_at.is_(None), User.is_active.is_(True))
            .order_by(User.created_at)
        )
        return list(rows.scalars())

    async def pending_registration(self, user_id: uuid.UUID) -> User | None:
        return (
            await self._session.execute(
                select(User).where(User.id == user_id, User.approved_at.is_(None)).with_for_update()
            )
        ).scalar_one_or_none()

    async def role_by_key(self, key: str) -> Role | None:
        return (
            await self._session.execute(select(Role).where(Role.key == key))
        ).scalar_one_or_none()

    def add_role(self, user_id: uuid.UUID, role_id: uuid.UUID, by: uuid.UUID) -> None:
        self._session.add(UserRole(user_id=user_id, role_id=role_id, assigned_by_id=by))

    async def delete(self, user: User) -> None:
        await self._session.delete(user)
        await self._session.flush()


class PeopleRepository:
    """People core. The organisation is small, so lists load whole tables and the
    service joins in memory (one query per table, no N+1)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------ employees

    async def employees(self) -> list[Employee]:
        rows = await self._session.execute(select(Employee).order_by(Employee.full_name))
        return list(rows.scalars())

    async def employee(self, employee_id: uuid.UUID, *, lock: bool = False) -> Employee | None:
        stmt = select(Employee).where(Employee.id == employee_id)
        if lock:
            stmt = stmt.with_for_update()
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def employee_for_user(self, user_id: uuid.UUID) -> Employee | None:
        stmt = select(Employee).where(Employee.user_id == user_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def by_official_email(
        self, email: str, *, exclude: uuid.UUID | None = None
    ) -> Employee | None:
        stmt = select(Employee).where(Employee.official_email == email)
        if exclude is not None:
            stmt = stmt.where(Employee.id != exclude)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    # ------------------------------------------------------------ organisation

    async def departments(self) -> list[Department]:
        rows = await self._session.execute(select(Department).order_by(Department.name))
        return list(rows.scalars())

    async def department(self, department_id: uuid.UUID) -> Department | None:
        return await self._session.get(Department, department_id)

    async def department_by_name(self, name: str) -> Department | None:
        stmt = select(Department).where(Department.name == name)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def designations(self) -> list[Designation]:
        rows = await self._session.execute(select(Designation).order_by(Designation.name))
        return list(rows.scalars())

    async def designation(self, designation_id: uuid.UUID) -> Designation | None:
        return await self._session.get(Designation, designation_id)

    async def designation_by_name(
        self, name: str, department_id: uuid.UUID | None
    ) -> Designation | None:
        stmt = select(Designation).where(
            Designation.name == name,
            Designation.department_id.is_(None)
            if department_id is None
            else Designation.department_id == department_id,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    # ------------------------------------------------------------ reporting lines

    async def open_lines(self) -> list[ReportingLine]:
        rows = await self._session.execute(
            select(ReportingLine)
            .where(ReportingLine.ends_on.is_(None))
            .order_by(ReportingLine.starts_on, ReportingLine.created_at)
        )
        return list(rows.scalars())

    async def lines_for(self, employee_id: uuid.UUID) -> list[ReportingLine]:
        """Every line of the employee, ended ones included, newest first."""
        rows = await self._session.execute(
            select(ReportingLine)
            .where(ReportingLine.employee_id == employee_id)
            .order_by(ReportingLine.starts_on.desc(), ReportingLine.created_at.desc())
        )
        return list(rows.scalars())

    async def owners(self) -> list[DepartmentOwner]:
        rows = await self._session.execute(
            select(DepartmentOwner).order_by(DepartmentOwner.created_at)
        )
        return list(rows.scalars())

    async def replace_owners(
        self, department_id: uuid.UUID, owner_ids: list[uuid.UUID], by: uuid.UUID
    ) -> None:
        await self._session.execute(
            delete(DepartmentOwner).where(DepartmentOwner.department_id == department_id)
        )
        for owner_id in owner_ids:
            self._session.add(
                DepartmentOwner(department_id=department_id, employee_id=owner_id, created_by_id=by)
            )
        await self._session.flush()

    # ------------------------------------------------------------ projects (read only)

    async def projects(self) -> list[Project]:
        rows = await self._session.execute(select(Project).order_by(Project.code))
        return list(rows.scalars())

    async def project(self, project_id: uuid.UUID) -> Project | None:
        return await self._session.get(Project, project_id)

    # ------------------------------------------------------------ personal, history, users

    async def personal(self, employee_id: uuid.UUID) -> EmployeePersonal | None:
        return await self._session.get(EmployeePersonal, employee_id)

    async def events(self, employee_id: uuid.UUID) -> list[tuple[EmploymentEvent, User | None]]:
        rows = await self._session.execute(
            select(EmploymentEvent, User)
            .outerjoin(User, User.id == EmploymentEvent.actor_user_id)
            .where(EmploymentEvent.employee_id == employee_id)
            .order_by(EmploymentEvent.occurred_at.desc(), EmploymentEvent.id)
        )
        return [(event, user) for event, user in rows.all()]

    async def user(self, user_id: uuid.UUID) -> User | None:
        return await self._session.get(User, user_id)

    async def unlinked_users(self) -> list[User]:
        linked = select(Employee.user_id).where(Employee.user_id.is_not(None))
        rows = await self._session.execute(
            select(User)
            .where(User.is_active.is_(True), User.approved_at.is_not(None), User.id.not_in(linked))
            .order_by(User.full_name)
        )
        return list(rows.scalars())

    async def users(self, ids: set[uuid.UUID]) -> dict[uuid.UUID, User]:
        if not ids:
            return {}
        rows = await self._session.execute(select(User).where(User.id.in_(ids)))
        return {u.id: u for u in rows.scalars()}

    def add(
        self,
        obj: Employee
        | EmployeePersonal
        | ReportingLine
        | EmploymentEvent
        | Department
        | Designation,
    ) -> None:
        self._session.add(obj)

    async def flush(self) -> None:
        await self._session.flush()


class RoleRepository:
    """Role definitions and user-role assignments (Organization & Role Settings)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def roles(self) -> list[Role]:
        rows = await self._session.execute(select(Role).order_by(Role.name))
        return list(rows.scalars())

    async def role(self, key: str, *, lock: bool = False) -> Role | None:
        stmt = select(Role).where(Role.key == key)
        if lock:
            stmt = stmt.with_for_update()
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def member_counts(self) -> dict[uuid.UUID, int]:
        rows = await self._session.execute(
            select(UserRole.role_id, func.count()).group_by(UserRole.role_id)
        )
        return {role_id: count for role_id, count in rows.all()}  # noqa: C416

    async def users(self) -> list[User]:
        """Approved, active sign-in accounts."""
        rows = await self._session.execute(
            select(User)
            .where(User.is_active.is_(True), User.approved_at.is_not(None))
            .order_by(User.full_name)
        )
        return list(rows.scalars())

    async def user(self, user_id: uuid.UUID) -> User | None:
        return await self._session.get(User, user_id)

    async def assignments(self) -> list[tuple[uuid.UUID, str]]:
        rows = await self._session.execute(
            select(UserRole.user_id, Role.key).join(Role, Role.id == UserRole.role_id)
        )
        return [(user_id, key) for user_id, key in rows.all()]

    async def set_roles(self, user_id: uuid.UUID, roles: list[Role], by: uuid.UUID) -> None:
        await self._session.execute(delete(UserRole).where(UserRole.user_id == user_id))
        for role in roles:
            self._session.add(UserRole(user_id=user_id, role_id=role.id, assigned_by_id=by))
        await self._session.flush()

    def add(self, role: Role) -> None:
        self._session.add(role)

    async def flush(self) -> None:
        await self._session.flush()


#: Audit actions that belong to the organisation audit log.
ORG_AUDIT_PREFIXES = ("department.", "designation.", "reporting.", "role.", "user.roles")
ORG_AUDIT_ACTIONS = ("employee.created", "employee.placement_changed")


class OrgAuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def entries(
        self, *, limit: int, action: str | None = None
    ) -> list[tuple[AuditLog, User | None]]:
        conditions = [AuditLog.action.like(f"{p}%") for p in ORG_AUDIT_PREFIXES]
        conditions.append(AuditLog.action.in_(ORG_AUDIT_ACTIONS))
        stmt = (
            select(AuditLog, User)
            .outerjoin(User, User.id == AuditLog.actor_user_id)
            .where(or_(*conditions))
            .order_by(AuditLog.occurred_at.desc(), AuditLog.id)
            .limit(limit)
        )
        if action:
            stmt = stmt.where(AuditLog.action.like(f"{action}%"))
        return [(entry, user) for entry, user in (await self._session.execute(stmt)).all()]
