"""Task versions and approvals (interim shape from the clickable demo).

TODO(pilot-port): reconcile with schema.prisma.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Final

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKey

STAGES: Final = ("internal", "client")
CHANNELS: Final = ("email", "call", "meeting", "whatsapp")


class TaskVersion(UUIDPrimaryKey, Base):
    """One submission of a task's work for review (v1, v2, …)."""

    __tablename__ = "task_versions"
    __mapper_args__ = {"eager_defaults": True}  # noqa: RUF012
    __table_args__ = (Index("uq_task_versions_task_id_number", "task_id", "number", unique=True),)

    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    link: Mapped[str | None] = mapped_column(String(500))
    submitted_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    submitted_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())


class Approval(UUIDPrimaryKey, Base):
    """A request for a decision on one version, internal (reviewer) or client (via the AM)."""

    __tablename__ = "approvals"
    __mapper_args__ = {"eager_defaults": True}  # noqa: RUF012
    __table_args__ = (
        CheckConstraint("stage IN ('internal', 'client')", name="stage"),
        CheckConstraint(
            "status IN ('submitted', 'approved', 'changes', 'cancelled')", name="status"
        ),
        CheckConstraint(
            "client_channel IS NULL OR client_channel IN ('email', 'call', 'meeting', 'whatsapp')",
            name="client_channel",
        ),
        # At most one open request per task.
        Index(
            "uq_approvals_task_id_open",
            "task_id",
            unique=True,
            postgresql_where=text("status = 'submitted'"),
        ),
        Index("ix_approvals_status_approver_id", "status", "approver_id"),
        Index("ix_approvals_client_id", "client_id"),
    )

    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("task_versions.id", ondelete="CASCADE"), nullable=False
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False
    )
    stage: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default=text("'submitted'")
    )
    #: Internal stage: the task's reviewer. Client stage: NULL (the client's AM records it).
    approver_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    requested_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    decided_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    decided_at: Mapped[datetime | None]
    decision_note: Mapped[str | None] = mapped_column(Text)
    #: Client stage: who at the client decided, and how they told us.
    client_decider: Mapped[str | None] = mapped_column(String(200))
    client_channel: Mapped[str | None] = mapped_column(String(10))
