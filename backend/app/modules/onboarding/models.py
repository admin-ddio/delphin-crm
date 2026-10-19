"""Onboarding tables (interim shape from the clickable demo's 13-step workflow).

TODO(pilot-port): reconcile with the onboarding models in schema.prisma.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKey


class ClientOnboarding(Base):
    """One row per client: the state of steps 1, 4–5, 9–12."""

    __tablename__ = "client_onboarding"
    __mapper_args__ = {"eager_defaults": True}  # noqa: RUF012
    __table_args__ = (
        CheckConstraint("contract IN ('none', 'draft', 'signed')", name="contract"),
        CheckConstraint("questionnaire IN ('none', 'sent', 'submitted')", name="questionnaire"),
        CheckConstraint("kickoff_client IN ('none', 'scheduled', 'done')", name="kickoff_client"),
        CheckConstraint(
            "kickoff_internal IN ('none', 'scheduled', 'done')", name="kickoff_internal"
        ),
    )

    client_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"), primary_key=True
    )
    contract: Mapped[str] = mapped_column(String(10), nullable=False, server_default=text("'none'"))
    contract_signed_at: Mapped[datetime | None]
    questionnaire: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default=text("'none'")
    )
    questionnaire_sent_at: Mapped[datetime | None]
    questionnaire_submitted_at: Mapped[datetime | None]
    questionnaire_answers: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    kickoff_client: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default=text("'none'")
    )
    kickoff_client_at: Mapped[datetime | None]
    kickoff_client_notes: Mapped[str | None] = mapped_column(Text)
    kickoff_internal: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default=text("'none'")
    )
    kickoff_internal_at: Mapped[datetime | None]
    kickoff_internal_notes: Mapped[str | None] = mapped_column(Text)
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
    position: Mapped[int] = mapped_column(nullable=False, server_default=text("0"))
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'pending'")
    )
    verified_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    verified_at: Mapped[datetime | None]
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
    baseline: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    target: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit: Mapped[str] = mapped_column(String(60), nullable=False)
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
