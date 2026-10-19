"""Projects (interim shape from the clickable demo).

TODO(pilot-port): reconcile with schema.prisma.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamped, UUIDPrimaryKey


class Project(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "projects"
    __mapper_args__ = {"eager_defaults": True}  # noqa: RUF012
    __table_args__ = (
        Index("ix_projects_client_id", "client_id"),
        Index("ix_projects_manager_id", "manager_id"),
    )

    code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    client_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False
    )
    manager_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    start_date: Mapped[date] = mapped_column(nullable=False)
    template: Mapped[str | None] = mapped_column(String(50))
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
