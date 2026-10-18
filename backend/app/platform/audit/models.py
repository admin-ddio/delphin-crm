"""audit_log table.

actor_user_id deliberately has no foreign key: an ON DELETE action would have to
UPDATE audit rows, which the append-only trigger forbids, and history must
outlive the users it mentions.

TODO(pilot-port): reconcile with AuditLog in schema.prisma and its trigger migration.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Index, String, func, text
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKey


class AuditLog(UUIDPrimaryKey, Base):
    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_log_entity_type_entity_id", "entity_type", "entity_id"),
        Index("ix_audit_log_actor_user_id", "actor_user_id"),
        Index("ix_audit_log_occurred_at", "occurred_at"),
    )

    occurred_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    actor_user_id: Mapped[uuid.UUID | None]
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(100))
    request_id: Mapped[str | None] = mapped_column(String(128))
    ip: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(String(500))
    changes: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    context: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
