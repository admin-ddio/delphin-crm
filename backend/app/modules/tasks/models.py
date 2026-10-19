"""Tasks (interim shape from the clickable demo). TODO(pilot-port): reconcile with schema.prisma."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Final

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    false,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamped, UUIDPrimaryKey

#: Workflow order (= kanban columns + cancelled), from the demo.
TASK_STATUSES: Final = (
    "backlog",
    "ready",
    "in_progress",
    "blocked",
    "internal_review",
    "client_approval",
    "completed",
    "cancelled",
)
CLOSED_STATUSES: Final = frozenset({"completed", "cancelled"})


class Task(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "tasks"
    __mapper_args__ = {"eager_defaults": True}  # noqa: RUF012
    __table_args__ = (
        CheckConstraint(
            "status IN ('backlog', 'ready', 'in_progress', 'blocked', 'internal_review', "
            "'client_approval', 'completed', 'cancelled')",
            name="status",
        ),
        Index("ix_tasks_project_id_status", "project_id", "status"),
        Index("ix_tasks_assignee_id_status", "assignee_id", "status"),
        Index("ix_tasks_client_id", "client_id"),
    )

    number: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'backlog'")
    )
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    requires_review: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
    requires_client_approval: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=false()
    )
    due_date: Mapped[date | None]
    completed_at: Mapped[datetime | None]
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
