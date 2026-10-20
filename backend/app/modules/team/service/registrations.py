"""Approving self sign-ups.

Sign-up approval rules:
- only actors with `users.approve` see or decide pending sign-ups (router guard);
- approving assigns exactly one existing role and records who approved and when;
- rejecting deletes the pending app user AND its Firebase account, so the e-mail
  can register again later; both decisions are audited.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.actor import Actor
from app.core.clock import Clock
from app.core.errors import NotFound, ValidationFailed
from app.modules.team.repository import TeamRepository
from app.modules.team.schemas import PendingRegistration
from app.platform.audit.service import AuditWriter
from app.platform.identity.firebase import IdentityProvider
from app.platform.identity.models import User


class TeamService:
    def __init__(self, session: AsyncSession, *, clock: Clock, identity: IdentityProvider) -> None:
        self._repo = TeamRepository(session)
        self._clock = clock
        self._identity = identity
        self._audit = AuditWriter(session)

    async def pending_registrations(self) -> list[PendingRegistration]:
        result = []
        for user in await self._repo.pending_registrations():
            verified = (
                await self._identity.email_verified(user.firebase_uid)
                if user.firebase_uid
                else None
            )
            result.append(
                PendingRegistration(
                    id=user.id,
                    email=user.email,
                    full_name=user.full_name,
                    registered_at=user.created_at,
                    email_verified=verified,
                )
            )
        return result

    async def approve(self, actor: Actor, user_id: uuid.UUID, role_key: str) -> None:
        user = await self._pending(user_id)
        role = await self._repo.role_by_key(role_key)
        if role is None:
            raise ValidationFailed(f"Unknown role '{role_key}'.", details={"role": role_key})
        user.approved_at = self._clock.now()
        user.approved_by_id = actor.user_id
        self._repo.add_role(user.id, role.id, actor.user_id)
        await self._audit.record(
            action="team.registration_approved",
            entity_type="user",
            entity_id=user.id,
            actor_user_id=actor.user_id,
            context={"role": role_key, "email": user.email},
        )

    async def reject(self, actor: Actor, user_id: uuid.UUID) -> None:
        user = await self._pending(user_id)
        email, uid = user.email, user.firebase_uid
        await self._repo.delete(user)
        if uid:
            await self._identity.delete_user(uid)
        await self._audit.record(
            action="team.registration_rejected",
            entity_type="user",
            entity_id=user_id,
            actor_user_id=actor.user_id,
            context={"email": email},
        )

    async def _pending(self, user_id: uuid.UUID) -> User:
        user = await self._repo.pending_registration(user_id)
        if user is None:
            raise NotFound("This sign-up was not found or has already been handled.")
        return user
