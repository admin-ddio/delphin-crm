"""Queries for the auth module."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.identity.models import Role, User, UserRole


class AuthRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def user_by_email(self, email: str) -> User | None:
        # users.email is citext: the comparison is case-insensitive.
        return (
            await self._session.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()

    async def user_by_firebase_uid(self, uid: str) -> User | None:
        return (
            await self._session.execute(select(User).where(User.firebase_uid == uid))
        ).scalar_one_or_none()

    async def role_by_key(self, key: str) -> Role | None:
        return (
            await self._session.execute(select(Role).where(Role.key == key))
        ).scalar_one_or_none()

    def add(self, obj: User | UserRole) -> None:
        self._session.add(obj)

    async def flush(self) -> None:
        await self._session.flush()
