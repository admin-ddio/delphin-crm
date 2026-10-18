"""Queries for the team module."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.identity.models import Role, User, UserRole


class TeamRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def pending_registrations(self) -> list[User]:
        rows = await self._session.execute(
            select(User)
            .where(User.approved_at.is_(None), User.is_active.is_(True))
            .order_by(User.created_at)
        )
        return list(rows.scalars())

    async def pending_registration(self, user_id: uuid.UUID) -> User | None:
        return (
            await self._session.execute(
                select(User).where(User.id == user_id, User.approved_at.is_(None)).with_for_update()
            )
        ).scalar_one_or_none()

    async def role_by_key(self, key: str) -> Role | None:
        return (
            await self._session.execute(select(Role).where(Role.key == key))
        ).scalar_one_or_none()

    def add_role(self, user_id: uuid.UUID, role_id: uuid.UUID, by: uuid.UUID) -> None:
        self._session.add(UserRole(user_id=user_id, role_id=role_id, assigned_by_id=by))

    async def delete(self, user: User) -> None:
        await self._session.delete(user)
        await self._session.flush()
