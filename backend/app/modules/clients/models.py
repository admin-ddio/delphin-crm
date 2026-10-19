"""SQLAlchemy models for the clients module.

INTERIM shape from the clickable demo (create form + client list). TODO(pilot-port):
reconcile with the Client model in schema.prisma (contacts, lifecycle enum, etc.).
"""

from __future__ import annotations

import uuid
from typing import Final

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamped, UUIDPrimaryKey

# Demo list badges: "Contract pending" → "Onboarding" → "Active". Onboarding moves it.
CLIENT_STATUSES: Final = ("contract_pending", "onboarding", "active")


class Client(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "clients"
    # Fetch server-set values (updated_at, defaults) in the same statement: no lazy loads in async.
    __mapper_args__ = {"eager_defaults": True}  # noqa: RUF012
    __table_args__ = (
        CheckConstraint("status IN ('contract_pending', 'onboarding', 'active')", name="status"),
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
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default=text("'contract_pending'")
    )
    account_manager_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
