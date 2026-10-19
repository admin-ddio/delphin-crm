"""clients: CRM client records (interim shape from the clickable demo)

Revision ID: 0004_clients
Revises: 0003_users_approval
Create Date: 2026-10-18
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0004_clients"
down_revision: str | None = "0003_users_approval"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "clients",
        sa.Column(
            "id", pg.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("normalized_name", sa.String(200), nullable=False),
        sa.Column("website", sa.String(300), nullable=True),
        sa.Column("domain", sa.String(253), nullable=True),
        sa.Column("industry", sa.String(120), nullable=True),
        sa.Column("contact_name", sa.String(200), nullable=True),
        sa.Column("contact_email", sa.String(320), nullable=True),
        sa.Column(
            "status",
            sa.String(30),
            server_default=sa.text("'contract_pending'"),
            nullable=False,
        ),
        sa.Column("account_manager_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('contract_pending', 'onboarding', 'active')",
            name=op.f("ck_clients_status"),
        ),
        sa.ForeignKeyConstraint(
            ["account_manager_id"],
            ["users.id"],
            name=op.f("fk_clients_account_manager_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_clients_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_clients")),
        sa.UniqueConstraint("code", name=op.f("uq_clients_code")),
    )
    op.create_index(
        "uq_clients_domain",
        "clients",
        ["domain"],
        unique=True,
        postgresql_where=sa.text("domain IS NOT NULL"),
    )
    op.create_index("ix_clients_normalized_name", "clients", ["normalized_name"])
    op.create_index("ix_clients_account_manager_id", "clients", ["account_manager_id"])


def downgrade() -> None:
    op.drop_index("ix_clients_account_manager_id", table_name="clients")
    op.drop_index("ix_clients_normalized_name", table_name="clients")
    op.drop_index("uq_clients_domain", table_name="clients")
    op.drop_table("clients")
