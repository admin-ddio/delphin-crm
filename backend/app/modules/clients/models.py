"""SQLAlchemy models for the clients module.

INTERIM shape from the clickable demo (create form + client list). TODO(pilot-port):
reconcile with the Client model in schema.prisma (contacts, lifecycle enum, etc.).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Final

from sqlalchemy import CheckConstraint, ForeignKey, Index, Numeric, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamped, UUIDPrimaryKey

# Mockups (2026-10-19): Onboarding → Active (onboarding completion moves it); the AM can
# put a client On hold or mark the engagement Completed, and reactivate it.
CLIENT_STATUSES: Final = ("onboarding", "active", "on_hold", "completed")
BUSINESS_TYPES: Final = ("b2b", "b2c", "b2b_b2c", "d2c", "non_profit", "government")
COMPANY_SIZES: Final = ("1-10", "11-50", "51-200", "201-500", "501-1000", "1000+")
PAYMENT_TERMS: Final = ("monthly", "quarterly", "half_yearly", "annually", "one_time", "milestone")
TEAM_AREAS: Final = (
    "account",
    "project_management",
    "seo",
    "content",
    "design",
    "development",
    "social",
    "analytics",
)


class Client(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "clients"
    # Fetch server-set values (updated_at, defaults) in the same statement: no lazy loads in async.
    __mapper_args__ = {"eager_defaults": True}  # noqa: RUF012
    __table_args__ = (
        CheckConstraint(
            "status IN ('onboarding', 'active', 'on_hold', 'completed')", name="status"
        ),
        CheckConstraint(
            "contract_end IS NULL OR contract_start IS NULL OR contract_end >= contract_start",
            name="contract_dates",
        ),
        # One client per website domain (the hard duplicate rule), race-safe.
        Index(
            "uq_clients_domain",
            "domain",
            unique=True,
            postgresql_where=text("domain IS NOT NULL"),
        ),
        Index("ix_clients_normalized_name", "normalized_name"),
        Index("ix_clients_account_manager_id", "account_manager_id"),
    )

    code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(200), nullable=False)
    website: Mapped[str | None] = mapped_column(String(300))
    domain: Mapped[str | None] = mapped_column(String(253))
    industry: Mapped[str | None] = mapped_column(String(120))
    contact_name: Mapped[str | None] = mapped_column(String(200))
    contact_email: Mapped[str | None] = mapped_column(String(320))
    # Company information (create form).
    description: Mapped[str | None] = mapped_column(Text)
    business_type: Mapped[str | None] = mapped_column(String(20))
    company_size: Mapped[str | None] = mapped_column(String(20))
    #: ISO 3166-1 alpha-2.
    country: Mapped[str | None] = mapped_column(String(2))
    # Primary contact.
    contact_designation: Mapped[str | None] = mapped_column(String(120))
    contact_phone: Mapped[str | None] = mapped_column(String(40))
    contact_alt_email: Mapped[str | None] = mapped_column(String(320))
    contact_alt_phone: Mapped[str | None] = mapped_column(String(40))
    # Contract (captured at creation: onboarding step 1).
    contract_start: Mapped[date | None]
    contract_end: Mapped[date | None]
    contract_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    contract_currency: Mapped[str] = mapped_column(
        String(3), nullable=False, server_default=text("'INR'")
    )
    payment_terms: Mapped[str | None] = mapped_column(String(20))
    contract_notes: Mapped[str | None] = mapped_column(String(250))
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default=text("'onboarding'")
    )
    account_manager_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


class ClientTeamMember(Base):
    """People working on a client (assigned during onboarding, step 10).

    Also widens visibility: team members see the client even without clients.view_all.
    """

    __tablename__ = "client_team_members"
    __table_args__ = (
        CheckConstraint(
            "area IS NULL OR area IN ('account', 'project_management', 'seo', 'content', "
            "'design', 'development', 'social', 'analytics')",
            name="area",
        ),
        CheckConstraint("allocation IS NULL OR allocation BETWEEN 0 AND 100", name="allocation"),
    )

    client_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    added_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    added_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    #: Service area covered (coverage panel), the person's role on this account,
    #: what they own, and how much of their time goes to it.
    area: Mapped[str | None] = mapped_column(String(30))
    role_title: Mapped[str | None] = mapped_column(String(100))
    responsibilities: Mapped[str | None] = mapped_column(Text)
    allocation: Mapped[int | None]
