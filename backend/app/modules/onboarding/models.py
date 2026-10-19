"""Onboarding tables (13-step workflow; shape from the product mockups, 2026-10-19).

The contract lives on the client (captured at creation); kickoffs are meetings
(app.modules.meetings). TODO(pilot-port): reconcile with schema.prisma.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    false,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKey


class ClientOnboarding(Base):
    """One row per client: questionnaire, KPI notes, review and completion."""

    __tablename__ = "client_onboarding"
    __mapper_args__ = {"eager_defaults": True}  # noqa: RUF012
    __table_args__ = (
        CheckConstraint("questionnaire IN ('none', 'sent', 'submitted')", name="questionnaire"),
        CheckConstraint(
            "questionnaire_source IS NULL OR questionnaire_source IN ('client', 'staff')",
            name="questionnaire_source",
        ),
    )

    client_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"), primary_key=True
    )
    questionnaire: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default=text("'none'")
    )
    questionnaire_sent_at: Mapped[datetime | None]
    questionnaire_submitted_at: Mapped[datetime | None]
    #: Who submitted: the client (public link) or staff on their behalf.
    questionnaire_source: Mapped[str | None] = mapped_column(String(10))
    #: Structured answers (see onboarding.questionnaire); drafts may be partial.
    questionnaire_answers: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    questionnaire_updated_at: Mapped[datetime | None]
    kpi_notes: Mapped[str | None] = mapped_column(Text)
    kpi_notes_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    kpi_notes_at: Mapped[datetime | None]
    reviewed_at: Mapped[datetime | None]
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    completed_at: Mapped[datetime | None]
    completed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )


class OnboardingAccessItem(UUIDPrimaryKey, Base):
    """Platform access checklist (steps 6–7). Never stores credentials."""

    __tablename__ = "onboarding_access_items"
    __mapper_args__ = {"eager_defaults": True}  # noqa: RUF012
    __table_args__ = (
        UniqueConstraint("client_id", "key"),
        CheckConstraint(
            "status IN ('pending', 'requested', 'received', 'verified', 'rejected', "
            "'not_required')",
            name="status",
        ),
    )

    client_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"), nullable=False
    )
    key: Mapped[str] = mapped_column(String(20), nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(300))
    position: Mapped[int] = mapped_column(nullable=False, server_default=text("0"))
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'pending'")
    )
    #: Added by the team for this client (the five defaults are not).
    is_custom: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
    requested_at: Mapped[datetime | None]
    received_at: Mapped[datetime | None]
    verified_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    verified_at: Mapped[datetime | None]
    notes: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )


class OnboardingKpi(UUIDPrimaryKey, Base):
    """KPI target (step 8). Confirmation records who at the client agreed and how."""

    __tablename__ = "onboarding_kpis"
    __mapper_args__ = {"eager_defaults": True}  # noqa: RUF012
    __table_args__ = (Index("ix_onboarding_kpis_client_id", "client_id"),)

    client_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"), nullable=False
    )
    metric: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(200))
    baseline: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    target: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit: Mapped[str] = mapped_column(String(60), nullable=False)
    target_date: Mapped[date | None]
    current_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    current_updated_at: Mapped[datetime | None]
    confirmed_by_name: Mapped[str | None] = mapped_column(String(200))
    confirmed_via: Mapped[str | None] = mapped_column(String(30))
    confirmed_at: Mapped[datetime | None]
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())


class QuestionnaireLink(UUIDPrimaryKey, Base):
    """Single-use link the client opens to answer the questionnaire (step 4). Stored hashed."""

    __tablename__ = "onboarding_questionnaire_links"
    __table_args__ = (Index("ix_onboarding_questionnaire_links_client_id", "client_id"),)

    client_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    used_at: Mapped[datetime | None]
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
