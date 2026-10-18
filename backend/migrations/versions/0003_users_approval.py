"""users.approved_at / approved_by_id: self sign-ups wait for admin approval

Existing users were all invited, so they are backfilled as approved.

Revision ID: 0003_users_approval
Revises: 0002_users_firebase_uid
Create Date: 2026-10-16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0003_users_approval"
down_revision: str | None = "0002_users_firebase_uid"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("approved_by_id", pg.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        op.f("fk_users_approved_by_id_users"),
        "users",
        "users",
        ["approved_by_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.execute("UPDATE users SET approved_at = created_at WHERE approved_at IS NULL")


def downgrade() -> None:
    op.drop_constraint(op.f("fk_users_approved_by_id_users"), "users", type_="foreignkey")
    op.drop_column("users", "approved_by_id")
    op.drop_column("users", "approved_at")
