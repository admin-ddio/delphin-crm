"""People core and organization structure.

Departments (with executive owners and a default delivery manager), designations
(job titles: they never grant CRM permissions), employees, typed reporting lines
with effective dates, and employment events. Interim shape from the HR and
Organization Structure briefs (backend/app/modules/team/PARITY.md).
An employee may be linked to one `users` account; accounts are never duplicated.
Personal information lives in its own table so it can be access-controlled apart
from the directory. TODO(pilot-port): reconcile with schema.prisma.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Final

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    Text,
    false,
    func,
    text,
    true,
)
from sqlalchemy.dialects.postgresql import CITEXT, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamped, UUIDPrimaryKey

EMPLOYMENT_TYPES: Final = ("full_time", "part_time", "intern", "contractor", "consultant")
WORK_ARRANGEMENTS: Final = ("remote", "hybrid", "office")
EMPLOYEE_STATUSES: Final = ("onboarding", "probation", "active", "notice", "on_hold", "exited")
#: Organization brief §6. Each is independent of the others and of system roles.
REPORTING_KINDS: Final = (
    "direct_manager",
    "functional_manager",
    "project_manager",
    "department_head",
    "leave_approver",
    "performance_reviewer",
    "executive_escalation",
)
#: Kinds where several managers may be active at once (others: one at a time).
MULTI_KINDS: Final = frozenset({"functional_manager", "project_manager"})


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class Department(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "departments"
    __mapper_args__ = {"eager_defaults": True}  # noqa: RUF012

    name: Mapped[str] = mapped_column(CITEXT(), nullable=False, unique=True)
    #: The department's purpose.
    description: Mapped[str | None] = mapped_column(Text)
    head_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL", use_alter=True)
    )
    #: Default Project Manager for members' delivery reporting (overridable per person).
    delivery_manager_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL", use_alter=True)
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true())


class DepartmentOwner(Base):
    """Executive owner(s) of a department: the default functional managers of its
    members (Design has two). Changes are audited."""

    __tablename__ = "department_owners"

    department_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("departments.id", ondelete="CASCADE"), primary_key=True
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), primary_key=True
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())


class Designation(UUIDPrimaryKey, Timestamped, Base):
    """A job title. It never grants CRM permissions (those come from roles)."""

    __tablename__ = "designations"
    __mapper_args__ = {"eager_defaults": True}  # noqa: RUF012
    __table_args__ = (
        # Same title may exist in two departments (e.g. "Technical Lead").
        Index(
            "uq_designations_department_id_name",
            "department_id",
            "name",
            unique=True,
            postgresql_nulls_not_distinct=True,
        ),
    )

    name: Mapped[str] = mapped_column(CITEXT(), nullable=False)
    #: None for company-level titles (e.g. Founder & CEO).
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL")
    )
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
    #: Shown at the executive level of the org chart (the founders).
    is_executive: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
    employment_type: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'full_time'")
    )
    work_arrangement: Mapped[str | None] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'onboarding'")
    )
    joining_date: Mapped[date | None]
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
    """A typed reporting relationship with an effective period.

    Ending a line sets `ends_on`; rows are never deleted, so history is kept.
    Single-valued kinds allow one open line per employee; functional and project
    lines allow several, but never the same manager (and project) twice.
    """

    __tablename__ = "reporting_lines"
    __mapper_args__ = {"eager_defaults": True}  # noqa: RUF012
    __table_args__ = (
        CheckConstraint(_in("kind", REPORTING_KINDS), name="kind"),
        CheckConstraint("employee_id <> manager_id", name="not_self"),
        CheckConstraint("ends_on IS NULL OR ends_on >= starts_on", name="period"),
        CheckConstraint("project_id IS NULL OR kind = 'project_manager'", name="project_kind"),
        Index(
            "uq_reporting_lines_single_open",
            "employee_id",
            "kind",
            unique=True,
            postgresql_where=text(
                "ends_on IS NULL AND kind NOT IN ('functional_manager', 'project_manager')"
            ),
        ),
        Index(
            "uq_reporting_lines_multi_open",
            "employee_id",
            "kind",
            "manager_id",
            "project_id",
            unique=True,
            postgresql_where=text("ends_on IS NULL"),
            postgresql_nulls_not_distinct=True,
        ),
        Index("ix_reporting_lines_manager_id", "manager_id"),
        Index("ix_reporting_lines_project_id", "project_id"),
    )

    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
    )
    manager_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    #: Project Manager lines may be tied to one project (CRM projects module).
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE")
    )
    starts_on: Mapped[date] = mapped_column(nullable=False, server_default=func.current_date())
    ends_on: Mapped[date | None]
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    ended_by_id: Mapped[uuid.UUID | None] = mapped_column(
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
