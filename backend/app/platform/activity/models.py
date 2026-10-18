"""activity_events table.

TODO(pilot-port): reconcile with the activity model in schema.prisma (it may carry
direct client/project references used by the client Activity tab).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKey


class ActivityEvent(UUIDPrimaryKey, Base):
    __tablename__ = "activity_events"
    __table_args__ = (
        Index("ix_activity_events_subject_type_subject_id", "subject_type", "subject_id"),
        Index("ix_activity_events_occurred_at", "occurred_at"),
    )

    occurred_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    verb: Mapped[str] = mapped_column(String(100), nullable=False)
    subject_type: Mapped[str] = mapped_column(String(100), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(100), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    context: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
