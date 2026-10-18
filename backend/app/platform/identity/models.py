"""Identity tables.

TODO(pilot-port): compare column-by-column with the User, Role, Session and token
models in reference/pilot/nextjs-app/prisma/schema.prisma and reconcile in a new
migration. These shapes follow the scaffold brief, not the pilot schema, which was
not available.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    false,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, CITEXT, INET
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamped, UUIDPrimaryKey


class User(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(CITEXT(), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    # Firebase Auth account (ADR-0009). Set at invitation, or linked by verified e-mail
    # on first sign-in. Firebase holds the credentials.
    firebase_uid: Mapped[str | None] = mapped_column(String(128), unique=True)
    # Unused since ADR-0009 (Firebase holds passwords); kept for a later cleanup migration.
    password_hash: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
    # Self sign-ups wait here (NULL) until an approver assigns a role. Invited users are
    # approved at invitation. A pending user can never open a session.
    approved_at: Mapped[datetime | None]
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    activated_at: Mapped[datetime | None]
    last_login_at: Mapped[datetime | None]
    failed_login_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    locked_until: Mapped[datetime | None]


Index("uq_users_email_lower", func.lower(User.email), unique=True)


class Role(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "roles"

    key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    permissions: Mapped[list[str]] = mapped_column(
        ARRAY(String(100)), nullable=False, server_default=text("'{}'::varchar[]")
    )
    # System roles come from the catalogue seed and cannot be deleted.
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())


class UserRole(Base):
    __tablename__ = "user_roles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("roles.id", ondelete="RESTRICT"), primary_key=True, index=True
    )
    assigned_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    assigned_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


class UserSession(UUIDPrimaryKey, Base):
    """Server-side session. Only the SHA-256 of the cookie token is stored."""

    __tablename__ = "sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(nullable=False, index=True)
    revoked_at: Mapped[datetime | None]
    ip: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(String(500))


class AuthToken(UUIDPrimaryKey, Base):
    """Single-use invite (activation) and password-reset tokens, stored hashed."""

    __tablename__ = "auth_tokens"
    __table_args__ = (CheckConstraint("purpose IN ('invite', 'password_reset')", name="purpose"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    used_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
