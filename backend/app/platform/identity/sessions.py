"""Server-side sessions (ADR-0003) and session -> Actor resolution.

The cookie carries an opaque random token; only its SHA-256 is stored. A session
resolves to an Actor only while it is unrevoked, unexpired and its user is active.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.actor import Actor
from app.core.clock import Clock
from app.core.security import generate_token, hash_token
from app.platform.identity.models import Role, User, UserRole, UserSession

# Bound writes from busy sessions: last_seen_at moves at most this often.
TOUCH_INTERVAL = timedelta(minutes=5)


async def actor_for_user(session: AsyncSession, user: User) -> Actor:
    """Build the Actor for `user`: permissions are the union of its roles' permissions."""
    roles = (
        await session.execute(
            select(Role)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user.id)
        )
    ).scalars()
    keys: set[str] = set()
    permissions: set[str] = set()
    for role in roles:
        keys.add(role.key)
        permissions.update(role.permissions)
    return Actor(
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        roles=frozenset(keys),
        permissions=frozenset(permissions),
    )


class SessionStore:
    def __init__(self, session: AsyncSession, clock: Clock, ttl: timedelta) -> None:
        self._session = session
        self._clock = clock
        self._ttl = ttl

    async def create(
        self, user_id: uuid.UUID, *, ip: str | None = None, user_agent: str | None = None
    ) -> str:
        """Start a session; returns the raw token for the cookie (never stored)."""
        token = generate_token()
        now = self._clock.now()
        self._session.add(
            UserSession(
                user_id=user_id,
                token_hash=hash_token(token),
                created_at=now,
                last_seen_at=now,
                expires_at=now + self._ttl,
                ip=ip,
                user_agent=user_agent[:500] if user_agent else None,
            )
        )
        await self._session.flush()
        return token

    async def revoke(self, token: str) -> None:
        await self._session.execute(
            update(UserSession)
            .where(UserSession.token_hash == hash_token(token), UserSession.revoked_at.is_(None))
            .values(revoked_at=self._clock.now())
        )

    async def revoke_all(self, user_id: uuid.UUID, *, keep_token: str | None = None) -> None:
        """Revoke every live session of a user (optionally keeping the caller's own)."""
        stmt = (
            update(UserSession)
            .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
            .values(revoked_at=self._clock.now())
        )
        if keep_token is not None:
            stmt = stmt.where(UserSession.token_hash != hash_token(keep_token))
        await self._session.execute(stmt)


class DbActorResolver:
    """ActorResolver backed by the sessions table."""

    def __init__(self, clock: Clock) -> None:
        self._clock = clock

    async def resolve(self, session: AsyncSession, token: str) -> Actor | None:
        now = self._clock.now()
        row = (
            await session.execute(
                select(UserSession, User)
                .join(User, User.id == UserSession.user_id)
                .where(
                    UserSession.token_hash == hash_token(token),
                    UserSession.revoked_at.is_(None),
                    UserSession.expires_at > now,
                    User.is_active.is_(True),
                )
            )
        ).one_or_none()
        if row is None:
            return None
        user_session, user = row
        if now - user_session.last_seen_at > TOUCH_INTERVAL:
            user_session.last_seen_at = now
        return await actor_for_user(session, user)
