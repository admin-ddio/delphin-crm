"""Queries for the team module: sign-up approvals and people core."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.team.models import (
    Department,
    Designation,
    Employee,
    EmployeePersonal,
    EmploymentEvent,
    ReportingLine,
)
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

    async def designation_by_name(self, name: str) -> Designation | None:
        stmt = select(Designation).where(Designation.name == name)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    # ------------------------------------------------------------ reporting lines

    async def open_lines(self) -> list[ReportingLine]:
        rows = await self._session.execute(
            select(ReportingLine)
            .where(ReportingLine.ends_on.is_(None))
            .order_by(ReportingLine.starts_on, ReportingLine.created_at)
        )
        return list(rows.scalars())

    async def line(self, line_id: uuid.UUID) -> ReportingLine | None:
        return await self._session.get(ReportingLine, line_id)

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
