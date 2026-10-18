"""System tables.

TODO(pilot-port): reconcile with Setting, Counter, SavedView and IntegrationConfig
in reference/pilot/nextjs-app/prisma/schema.prisma.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    ForeignKey,
    LargeBinary,
    String,
    UniqueConstraint,
    false,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamped, UUIDPrimaryKey


class Setting(Base):
    """Key/value organisation settings (non-secret)."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


class Counter(Base):
    """Transactional sequence per key, used for human codes (CL-0001, INV-2026-0001)."""

    __tablename__ = "counters"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )


class SavedView(UUIDPrimaryKey, Timestamped, Base):
    """A user's saved list filters/sort for a resource."""

    __tablename__ = "saved_views"
    __table_args__ = (UniqueConstraint("owner_id", "resource", "name"),)

    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    resource: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    filters: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    sort: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    is_shared: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())


class IntegrationConfig(UUIDPrimaryKey, Timestamped, Base):
    """Per-provider integration settings (GSC, GA4, Ahrefs, Drive, SMTP, social).

    `config` holds non-secret options only. Credentials go in `encrypted_secrets`
    (encryption scheme lands with the first integration port).
    """

    __tablename__ = "integration_configs"

    provider: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
    config: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    encrypted_secrets: Mapped[bytes | None] = mapped_column(LargeBinary)
    last_verified_at: Mapped[datetime | None]
