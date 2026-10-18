"""job_runs table.

TODO(pilot-port): reconcile with the job run model in schema.prisma.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKey


class JobRun(UUIDPrimaryKey, Base):
    __tablename__ = "job_runs"
    __table_args__ = (
        CheckConstraint("status IN ('running', 'succeeded', 'failed', 'skipped')", name="status"),
        CheckConstraint("triggered_by IN ('cron', 'manual', 'system')", name="triggered_by"),
        Index("ix_job_runs_job_name_started_at", "job_name", "started_at"),
    )

    job_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    triggered_by: Mapped[str] = mapped_column(String(20), nullable=False)
    started_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    finished_at: Mapped[datetime | None]
    result: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    error: Mapped[str | None] = mapped_column(Text)
