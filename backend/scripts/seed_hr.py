"""Idempotently add Delphin Digital's leadership team to the people core (development).

From the HR brief: Hanumesh JK (Founder & CEO), Vinay Kumar (COO, head of the SEO
Team), Shilpa R (Co-Founder), Neeta W (Project Manager). Vinay reports to Hanumesh.
Nothing else is assumed: Shilpa's and Neeta's reporting lines and departments, the
other department heads and every e-mail address are left for HR to set in the app.
Hanumesh's record is linked to an existing account with HANUMESH_EMAIL if present.

Run: docker compose run --rm -T backend python scripts/seed_hr.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.discovery import import_all_models
from app.modules.team.models import (
    Department,
    Designation,
    Employee,
    EmployeePersonal,
    EmploymentEvent,
    ReportingLine,
)
from app.platform.identity.models import User
from app.platform.system.counters import format_code, next_value


@dataclass(frozen=True)
class Person:
    name: str
    designation: str
    department: str | None = None
    manager: str | None = None


LEADERSHIP = (
    Person("Hanumesh JK", "Founder & CEO"),
    Person("Vinay Kumar", "COO", department="SEO Team", manager="Hanumesh JK"),
    Person("Shilpa R", "Co-Founder"),
    Person("Neeta W", "Project Manager"),
)
SEO_HEAD = "Vinay Kumar"


async def _one[T](session: AsyncSession, model: type[T], **where: object) -> T | None:
    stmt = select(model).filter_by(**where)
    return (await session.execute(stmt)).scalar_one_or_none()


async def seed(session: AsyncSession, owner_email: str) -> list[str]:
    done: list[str] = []
    people: dict[str, Employee] = {}
    for person in LEADERSHIP:
        employee = await _one(session, Employee, full_name=person.name)
        if employee is None:
            designation = await _one(session, Designation, name=person.designation)
            department = (
                await _one(session, Department, name=person.department)
                if person.department
                else None
            )
            employee = Employee(
                code=format_code("DD", await next_value(session, "employee")),
                full_name=person.name,
                designation_id=designation.id if designation else None,
                department_id=department.id if department else None,
                employment_type="full_time",
                status="active",
            )
            session.add(employee)
            await session.flush()
            session.add(EmployeePersonal(employee_id=employee.id))
            session.add(
                EmploymentEvent(
                    employee_id=employee.id,
                    kind="created",
                    summary=f"Employee record created: {person.designation} (seeded)",
                )
            )
            done.append(f"created {employee.code} {person.name}")
        people[person.name] = employee

    for person in LEADERSHIP:
        if person.manager is None:
            continue
        employee, manager = people[person.name], people[person.manager]
        line = await _one(
            session, ReportingLine, employee_id=employee.id, kind="direct", ends_on=None
        )
        if line is None:
            session.add(
                ReportingLine(employee_id=employee.id, manager_id=manager.id, kind="direct")
            )
            done.append(f"{person.name} reports to {person.manager}")

    seo = await _one(session, Department, name="SEO Team")
    if seo is not None and seo.head_id is None:
        seo.head_id = people[SEO_HEAD].id
        done.append(f"SEO Team head: {SEO_HEAD}")

    owner = people["Hanumesh JK"]
    user = await _one(session, User, email=owner_email)
    if (
        owner.user_id is None
        and user is not None
        and await _one(session, Employee, user_id=user.id) is None
    ):
        owner.user_id = user.id
        done.append(f"linked Hanumesh JK to {owner_email}")
    return done


async def main() -> int:
    import_all_models()
    engine = create_async_engine(os.environ["DATABASE_URL"])
    async with async_sessionmaker(engine, expire_on_commit=False)() as session, session.begin():
        done = await seed(session, os.environ.get("HANUMESH_EMAIL", "hanumesh.jk@gmail.com"))
    await engine.dispose()
    print("\n".join(done) if done else "nothing to do: already seeded")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
