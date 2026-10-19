"""Client meetings with attendees, agenda, notes and action items (product mockups).

Completed meetings of type `kickoff` and `internal` drive onboarding steps 9 and 10.
TODO(pilot-port): reconcile with schema.prisma.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Final

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, String, Text, false, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamped, UUIDPrimaryKey

MEETING_TYPES: Final = ("kickoff", "review", "planning", "internal", "reporting", "other")
MEETING_STATUSES: Final = ("scheduled", "completed", "cancelled")
PLATFORMS: Final = ("google_meet", "zoom", "teams", "phone", "in_person", "other")


class Meeting(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "meetings"
    __mapper_args__ = {"eager_defaults": True}  # noqa: RUF012
    __table_args__ = (
        CheckConstraint(
            "type IN ('kickoff', 'review', 'planning', 'internal', 'reporting', 'other')",
            name="type",
        ),
        CheckConstraint("status IN ('scheduled', 'completed', 'cancelled')", name="status"),
        CheckConstraint(
            "platform IS NULL OR platform IN "
            "('google_meet', 'zoom', 'teams', 'phone', 'in_person', 'other')",
            name="platform",
        ),
        CheckConstraint("ends_at > starts_at", name="times"),
        Index("ix_meetings_client_id_starts_at", "client_id", "starts_at"),
    )

    client_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(300))
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'scheduled'")
    )
    starts_at: Mapped[datetime] = mapped_column(nullable=False)
    ends_at: Mapped[datetime] = mapped_column(nullable=False)
    platform: Mapped[str | None] = mapped_column(String(20))
    location: Mapped[str | None] = mapped_column(String(500))
    agenda: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[datetime | None]
    cancelled_reason: Mapped[str | None] = mapped_column(String(300))
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


class MeetingAttendee(UUIDPrimaryKey, Base):
    """An internal user (user_id) or an external guest (name / e-mail)."""

    __tablename__ = "meeting_attendees"
    __table_args__ = (
        CheckConstraint("user_id IS NOT NULL OR name IS NOT NULL", name="who"),
        Index("ix_meeting_attendees_meeting_id", "meeting_id"),
    )

    meeting_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str | None] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(320))
    organisation: Mapped[str | None] = mapped_column(String(200))


class MeetingActionItem(UUIDPrimaryKey, Base):
    __tablename__ = "meeting_action_items"
    __mapper_args__ = {"eager_defaults": True}  # noqa: RUF012
    __table_args__ = (Index("ix_meeting_action_items_meeting_id", "meeting_id"),)

    meeting_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    due_date: Mapped[date | None]
    done: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
    done_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
