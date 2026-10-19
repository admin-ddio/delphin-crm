"""People core: departments, designations, employees, reporting lines, employment events.

Interim shape from the HR brief (docs: backend/app/modules/team/PARITY.md).
An employee may be linked to one `users` account; accounts are never duplicated.
Personal information lives in its own table so it can be access-controlled apart
from the directory. TODO(pilot-port): reconcile with schema.prisma.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Final

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, String, Text, func, text, true
from sqlalchemy.dialects.postgresql import CITEXT, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamped, UUIDPrimaryKey

EMPLOYMENT_TYPES: Final = ("full_time", "part_time", "intern", "contractor", "consultant")
WORK_ARRANGEMENTS: Final = ("remote", "hybrid", "office")
EMPLOYEE_STATUSES: Final = ("onboarding", "probation", "active", "notice", "on_hold", "exited")
REPORTING_KINDS: Final = ("direct", "dotted")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class Department(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "departments"
    __mapper_args__ = {"eager_defaults": True}  # noqa: RUF012

    name: Mapped[str] = mapped_column(CITEXT(), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    head_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL", use_alter=True)
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true())


class Designation(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "designations"
    __mapper_args__ = {"eager_defaults": True}  # noqa: RUF012

    name: Mapped[str] = mapped_column(CITEXT(), nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true())


class Employee(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "employees"
    __mapper_args__ = {"eager_defaults": True}  # noqa: RUF012
    __table_args__ = (
        CheckConstraint(_in("employment_type", EMPLOYMENT_TYPES), name="employment_type"),
        CheckConstraint(
            "work_arrangement IS NULL OR " + _in("work_arrangement", WORK_ARRANGEMENTS),
            name="work_arrangement",
        ),
        CheckConstraint(_in("status", EMPLOYEE_STATUSES), name="status"),
        CheckConstraint("leave_approver_id IS NULL OR leave_approver_id <> id", name="approver"),
        Index("ix_employees_department_id", "department_id"),
        Index("ix_employees_status", "status"),
    )

    #: Stable human ID, DD-0001… (never reused).
    code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), unique=True
    )
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    preferred_name: Mapped[str | None] = mapped_column(String(100))
    official_email: Mapped[str | None] = mapped_column(CITEXT(), unique=True)
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL")
    )
    designation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("designations.id", ondelete="SET NULL")
    )
    employment_type: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'full_time'")
    )
    work_arrangement: Mapped[str | None] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'onboarding'")
    )
    joining_date: Mapped[date | None]
    #: Who approves this person's leave (defaults to the direct manager when unset).
    leave_approver_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL")
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


class EmployeePersonal(Timestamped, Base):
    """Personal information: visible to the employee and to `hr.personal.view` only."""

    __tablename__ = "employee_personal"

    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), primary_key=True
    )
    personal_email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(40))
    date_of_birth: Mapped[date | None]
    current_address: Mapped[str | None] = mapped_column(Text)
    permanent_address: Mapped[str | None] = mapped_column(Text)
    emergency_name: Mapped[str | None] = mapped_column(String(200))
    emergency_relationship: Mapped[str | None] = mapped_column(String(100))
    emergency_phone: Mapped[str | None] = mapped_column(String(40))


class ReportingLine(UUIDPrimaryKey, Base):
    """Who reports to whom. One open direct line per employee; any number of dotted ones."""

    __tablename__ = "reporting_lines"
    __mapper_args__ = {"eager_defaults": True}  # noqa: RUF012
    __table_args__ = (
        CheckConstraint(_in("kind", REPORTING_KINDS), name="kind"),
        CheckConstraint("employee_id <> manager_id", name="not_self"),
        Index(
            "uq_reporting_lines_direct_open",
            "employee_id",
            unique=True,
            postgresql_where=text("kind = 'direct' AND ends_on IS NULL"),
        ),
        Index("ix_reporting_lines_manager_id", "manager_id"),
    )

    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
    )
    manager_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    starts_on: Mapped[date] = mapped_column(nullable=False, server_default=func.current_date())
    ends_on: Mapped[date | None]
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())


class EmploymentEvent(UUIDPrimaryKey, Base):
    """Employment history: joins, department/designation/manager/status changes."""

    __tablename__ = "employment_events"
    __mapper_args__ = {"eager_defaults": True}  # noqa: RUF012
    __table_args__ = (Index("ix_employment_events_employee_id", "employee_id", "occurred_at"),)

    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    changes: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    effective_on: Mapped[date | None]
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    #: clock_timestamp(), not now(): several events in one transaction keep their order.
    occurred_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.clock_timestamp()
    )
