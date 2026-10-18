"""users.firebase_uid: link app users to Firebase Auth accounts (ADR-0009)

Revision ID: 0002_users_firebase_uid
Revises: 0001_platform_core
Create Date: 2026-10-16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_users_firebase_uid"
down_revision: str | None = "0001_platform_core"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("firebase_uid", sa.String(128), nullable=True))
    op.create_unique_constraint(op.f("uq_users_firebase_uid"), "users", ["firebase_uid"])


def downgrade() -> None:
    op.drop_constraint(op.f("uq_users_firebase_uid"), "users", type_="unique")
    op.drop_column("users", "firebase_uid")
