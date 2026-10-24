"""Idempotently set up Delphin Digital's leadership and default reporting (development).

From the HR and Organization Structure briefs:
- Hanumesh JK (Founder & CEO), Vinay Kumar (Co-Founder & COO, head of the SEO Team)
  and Shilpa R (Co-Founder) are executive leadership; no founder reports to another
  (an earlier Vinay → Hanumesh direct line is ended, not deleted);
- Neeta W is a Project Manager in the Project Management Team and the default
  delivery Project Manager of the delivery departments;
- default functional reporting (department executive owners): Web and Application
  Development → Hanumesh; SEO and Social Media → Vinay; Design → both. Content,
  Performance Marketing, Project Management and Operations stay unassigned.
Existing choices are never overwritten: owners are only added to departments that
have none, and the delivery manager only where none is set. E-mail addresses are
left for HR. Hanumesh's record is linked to an existing account with HANUMESH_EMAIL.

Run: docker compose run --rm -T backend python scripts/seed_hr.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.discovery import import_all_models
from app.modules.team.models import (
    Department,
    DepartmentOwner,
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
    executive: bool = False


LEADERSHIP = (
    Person("Hanumesh JK", "Founder & CEO", executive=True),
    Person("Vinay Kumar", "Co-Founder & COO", department="SEO Team", executive=True),
    Person("Shilpa R", "Co-Founder", executive=True),
    Person("Neeta W", "Project Manager", department="Project Management Team"),
)
SEO_HEAD = "Vinay Kumar"
DEFAULT_PM = "Neeta W"
OWNERS = {
    "Web Development Team": ("Hanumesh JK",),
    "Application Development Team": ("Hanumesh JK",),
    "SEO Team": ("Vinay Kumar",),
    "Social Media Team": ("Vinay Kumar",),
    "Design Team": ("Hanumesh JK", "Vinay Kumar"),
}
DELIVERY = (
    "Web Development Team",
    "Application Development Team",
    "SEO Team",
    "Design Team",
    "Social Media Team",
    "Content Team",
    "Performance Marketing Team",
)


async def _one[T](session: AsyncSession, model: type[T], **where: object) -> T | None:
    stmt = select(model).filter_by(**where)
    return (await session.execute(stmt)).scalars().first()


async def _designation(
    session: AsyncSession, name: str, department: Department | None
) -> Designation | None:
    return await _one(
        session, Designation, name=name, department_id=department.id if department else None
    )


async def seed(session: AsyncSession, owner_email: str) -> list[str]:  # noqa: PLR0912, PLR0915
    done: list[str] = []
    people: dict[str, Employee] = {}
    for person in LEADERSHIP:
        department = (
            await _one(session, Department, name=person.department) if person.department else None
        )
        employee = await _one(session, Employee, full_name=person.name)
        if employee is None:
            designation = await _designation(session, person.designation, department)
            employee = Employee(
                code=format_code("DD", await next_value(session, "employee")),
                full_name=person.name,
                designation_id=designation.id if designation else None,
                department_id=department.id if department else None,
                employment_type="full_time",
                status="active",
                is_executive=person.executive,
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
        else:
            if person.executive and not employee.is_executive:
                employee.is_executive = True
                done.append(f"{person.name}: executive leadership")
            if department is not None and employee.department_id is None:
                employee.department_id = department.id
                done.append(f"{person.name}: {department.name}")
            designation = await _designation(session, person.designation, department)
            current = (
                await session.get(Designation, employee.designation_id)
                if employee.designation_id
                else None
            )
            # Only fix titles that are missing or the same title outside its department.
            fixable = designation and (current is None or current.name == designation.name)
            if fixable and designation and employee.designation_id != designation.id:
                employee.designation_id = designation.id
                done.append(f"{person.name}: {person.designation}")
        people[person.name] = employee
    await session.flush()

    # Founders sit side by side: end any direct line between two of them.
    founders = {
        p.id
        for name, p in people.items()
        if any(x.name == name and x.executive for x in LEADERSHIP)
    }
    lines = (
        await session.execute(
            select(ReportingLine).where(
                ReportingLine.ends_on.is_(None),
                ReportingLine.employee_id.in_(founders),
                ReportingLine.manager_id.in_(founders),
            )
        )
    ).scalars()
    for line in lines:
        line.ends_on = max(datetime.now(UTC).date(), line.starts_on)
        done.append("ended a reporting line between founders")

    for name, owner_names in OWNERS.items():
        department = await _one(session, Department, name=name)
        if department is None:
            continue
        existing = await _one(session, DepartmentOwner, department_id=department.id)
        if existing is not None:
            continue
        for owner_name in owner_names:
            session.add(
                DepartmentOwner(department_id=department.id, employee_id=people[owner_name].id)
            )
        done.append(f"{name}: functional owner(s) {' & '.join(owner_names)}")
    for name in DELIVERY:
        department = await _one(session, Department, name=name)
        if department is not None and department.delivery_manager_id is None:
            department.delivery_manager_id = people[DEFAULT_PM].id
            done.append(f"{name}: delivery via {DEFAULT_PM}")

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
