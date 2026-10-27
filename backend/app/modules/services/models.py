"""Services and retainers (interim shape from the services plan, 2026-10-27).

Delphin sells two kinds of service:
- retainers (monthly): SEO and Social Media; at most one active of each per client;
- projects (one-off): SEO-friendly Website, Web Application, Mobile Application.

`service_types` is the catalogue, `service_template_tasks` the editable task
templates (setup / monthly / delivery), `client_services` what a client bought
(chosen at client creation), and `service_occurrences` makes the monthly task
generation idempotent per (service, template task, YYYY-MM).
TODO(pilot-port): reconcile with schema.prisma (services/retainers.ts).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Final

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamped, UUIDPrimaryKey

SERVICE_KINDS: Final = ("retainer", "project")
TEMPLATE_PHASES: Final = ("setup", "monthly", "delivery")
SERVICE_STATUSES: Final = ("planned", "active", "paused", "completed", "cancelled")
#: Statuses that still count as "the client has this retainer".
OPEN_STATUSES: Final = ("planned", "active", "paused")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class ServiceType(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "service_types"
    __mapper_args__ = {"eager_defaults": True}  # noqa: RUF012
    __table_args__ = (CheckConstraint(_in("kind", SERVICE_KINDS), name="kind"),)

    key: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    #: Delivering department: its delivery manager is the default Project Manager.
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL")
    )
    sort: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true())


class ServiceTemplateTask(UUIDPrimaryKey, Timestamped, Base):
    """One task of a service template. Monthly tasks use `day_of_month`; setup and
    delivery tasks use offsets from the service's start date."""

    __tablename__ = "service_template_tasks"
    __mapper_args__ = {"eager_defaults": True}  # noqa: RUF012
    __table_args__ = (
        CheckConstraint(_in("phase", TEMPLATE_PHASES), name="phase"),
        CheckConstraint("(phase = 'monthly') = (day_of_month IS NOT NULL)", name="monthly_day"),
        CheckConstraint("day_of_month IS NULL OR day_of_month BETWEEN 1 AND 28", name="day"),
        CheckConstraint("start_offset_days >= 0 AND duration_days >= 0", name="offsets"),
        Index("ix_service_template_tasks_service_type_id", "service_type_id", "phase", "sort"),
    )

    service_type_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("service_types.id", ondelete="CASCADE"), nullable=False
    )
    phase: Mapped[str] = mapped_column(String(10), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    day_of_month: Mapped[int | None] = mapped_column(Integer)
    start_offset_days: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    duration_days: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    requires_review: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true())
    requires_client_approval: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    #: Client team area (seo, social, design, development, content…) for assignment.
    area: Mapped[str | None] = mapped_column(String(30))
    sort: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true())


class ServiceEngagement(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "client_services"
    __mapper_args__ = {"eager_defaults": True}  # noqa: RUF012
    __table_args__ = (
        CheckConstraint(_in("kind", SERVICE_KINDS), name="kind"),
        CheckConstraint(_in("status", SERVICE_STATUSES), name="status"),
        CheckConstraint(
            "end_date IS NULL OR start_date IS NULL OR end_date >= start_date", name="period"
        ),
        CheckConstraint("fee IS NULL OR fee >= 0", name="fee"),
        # One SEO and one Social retainer per client at a time.
        Index(
            "uq_client_services_open_retainer",
            "client_id",
            "service_type_id",
            unique=True,
            postgresql_where=text(
                "kind = 'retainer' AND status IN ('planned', 'active', 'paused')"
            ),
        ),
        Index("ix_client_services_client_id", "client_id"),
        Index("ix_client_services_status", "status"),
    )

    #: SRV-0001… from the transactional counter, never reused.
    code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    client_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"), nullable=False
    )
    service_type_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("service_types.id", ondelete="RESTRICT"), nullable=False
    )
    #: Copied from the service type so the partial unique index can use it.
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default=text("'planned'")
    )
    #: Monthly fee for retainers, the fixed price for projects (money roles only).
    fee: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default=text("'INR'"))
    notes: Mapped[str | None] = mapped_column(String(500))
    start_date: Mapped[date | None]
    end_date: Mapped[date | None]
    #: The delivery project created when the service starts.
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), unique=True
    )
    manager_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


class ServiceOccurrence(UUIDPrimaryKey, Base):
    """A monthly task already generated: generation is idempotent per period."""

    __tablename__ = "service_occurrences"
    __mapper_args__ = {"eager_defaults": True}  # noqa: RUF012
    __table_args__ = (
        UniqueConstraint(
            "client_service_id",
            "template_task_id",
            "occurrence_key",
            name="uq_service_occurrences_period",
        ),
    )

    client_service_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("client_services.id", ondelete="CASCADE"), nullable=False
    )
    template_task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("service_template_tasks.id", ondelete="CASCADE"), nullable=False
    )
    #: YYYY-MM
    occurrence_key: Mapped[str] = mapped_column(String(7), nullable=False)
    task_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tasks.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
