"""Sign-in via Firebase Auth, app sessions, invitations (ADR-0009).

Firebase verifies the password and the e-mail address; this service decides
whether that identity may use the app and opens the server-side session:

- the Firebase ID token must verify for our project;
- its e-mail must be verified;
- the person must have been invited (a row in `users`) and be active;
- the first sign-in links the Firebase uid to the invited user (matched by
  verified e-mail); afterwards the uid must match;
- every attempt is audited.

Credential rules (lockout after failed passwords, reset-link expiry, password
policy) are enforced by Firebase. TODO(pilot-port): compare with services/auth.ts.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.actor import Actor
from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import Conflict, NotFound, Unauthorized, ValidationFailed
from app.modules.auth.repository import AuthRepository
from app.platform.audit.service import AuditWriter
from app.platform.identity.firebase import IdentityProvider, InvalidIdentityTokenError
from app.platform.identity.models import User, UserRole
from app.platform.identity.sessions import SessionStore, actor_for_user

SignInFailure = Literal["invalid_token", "email_not_verified", "no_access", "pending_approval"]


@dataclass(frozen=True, slots=True)
class Registration:
    user: User
    created: bool


@dataclass(frozen=True, slots=True)
class RequestMeta:
    ip: str | None = None
    user_agent: str | None = None


@dataclass(frozen=True, slots=True)
class SignInResult:
    """Failures are returned, not raised, so their audit entries commit."""

    token: str | None = None
    actor: Actor | None = None
    failure: SignInFailure | None = None


@dataclass(frozen=True, slots=True)
class Invitation:
    user: User
    link: str


class AuthService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        clock: Clock,
        settings: Settings,
        identity: IdentityProvider,
    ) -> None:
        self._session = session
        self._repo = AuthRepository(session)
        self._clock = clock
        self._settings = settings
        self._identity = identity
        self._sessions = SessionStore(session, clock, timedelta(hours=settings.session_ttl_hours))
        self._audit = AuditWriter(session)

    # ------------------------------------------------------------ sessions

    async def start_session(self, id_token: str, meta: RequestMeta) -> SignInResult:
        try:
            claims = await self._identity.verify_id_token(id_token)
        except InvalidIdentityTokenError:
            await self._audit_auth("auth.login_failed", None, meta, reason="invalid_token")
            return SignInResult(failure="invalid_token")

        if not claims.email_verified or not claims.email:
            await self._audit_auth(
                "auth.login_failed", None, meta, reason="email_not_verified", uid=claims.uid
            )
            return SignInResult(failure="email_not_verified")

        user = await self._repo.user_by_firebase_uid(claims.uid)
        if user is None:
            user = await self._repo.user_by_email(claims.email)
            # An invited user already linked to a different Firebase account is not
            # taken over by whoever now holds that e-mail in Firebase.
            if user is not None and user.firebase_uid not in (None, claims.uid):
                user = None
        if user is None or not user.is_active:
            await self._audit_auth(
                "auth.login_failed",
                user.id if user else None,
                meta,
                reason="no_access",
                uid=claims.uid,
            )
            return SignInResult(failure="no_access")
        if user.approved_at is None:
            await self._audit_auth(
                "auth.login_failed", user.id, meta, reason="pending_approval", uid=claims.uid
            )
            return SignInResult(failure="pending_approval")

        now = self._clock.now()
        user.firebase_uid = claims.uid
        if user.activated_at is None:
            user.activated_at = now
        user.last_login_at = now
        token = await self._sessions.create(user.id, ip=meta.ip, user_agent=meta.user_agent)
        await self._audit_auth("auth.login", user.id, meta)
        return SignInResult(token=token, actor=await actor_for_user(self._session, user))

    async def sign_out(self, token: str, actor: Actor, meta: RequestMeta) -> None:
        await self._sessions.revoke(token)
        await self._audit_auth("auth.logout", actor.user_id, meta)

    async def revoke_other_sessions(self, actor: Actor, token: str, meta: RequestMeta) -> None:
        """Called after a password change in Firebase: sign out everywhere else."""
        await self._sessions.revoke_all(actor.user_id, keep_token=token)
        await self._audit_auth("auth.other_sessions_revoked", actor.user_id, meta)

    # ------------------------------------------------------------ self sign-up

    async def register(self, id_token: str, full_name: str, meta: RequestMeta) -> Registration:
        """Record a self sign-up as PENDING (no role, no access) until an approver acts.

        The Firebase account was just created in the browser; its e-mail need not be
        verified yet (sign-in will require it). Idempotent for the same Firebase account,
        so a retry after a network error doesn't fail.
        """
        try:
            claims = await self._identity.verify_id_token(id_token)
        except InvalidIdentityTokenError as exc:
            raise Unauthorized("Your sign-up could not be verified. Try again.") from exc
        if not claims.email:
            raise ValidationFailed("Your account has no e-mail address.")

        existing = await self._repo.user_by_firebase_uid(claims.uid)
        if existing is not None:
            return Registration(user=existing, created=False)
        if await self._repo.user_by_email(claims.email) is not None:
            raise Conflict("An account with this e-mail already exists. Sign in instead.")

        user = User(
            email=claims.email,
            full_name=full_name,
            firebase_uid=claims.uid,
            is_active=True,
            approved_at=None,
        )
        self._repo.add(user)
        await self._repo.flush()
        await self._audit_auth("auth.registered", user.id, meta)
        return Registration(user=user, created=True)

    # ------------------------------------------------------------ invitations

    async def invite(
        self,
        *,
        email: str,
        full_name: str,
        role_key: str,
        invited_by: uuid.UUID | None = None,
    ) -> Invitation:
        """Create the user (here and in Firebase) and a one-time password-setup link."""
        if await self._repo.user_by_email(email) is not None:
            raise Conflict("A user with this e-mail already exists.", details={"email": email})
        role = await self._repo.role_by_key(role_key)
        if role is None:
            raise NotFound(f"Role '{role_key}' does not exist. Run the config seed first.")
        uid = await self._identity.ensure_user(email, full_name)
        user = User(
            email=email,
            full_name=full_name,
            firebase_uid=uid,
            is_active=True,
            # An invitation is an approval.
            approved_at=self._clock.now(),
            approved_by_id=invited_by,
        )
        self._repo.add(user)
        await self._repo.flush()
        self._repo.add(UserRole(user_id=user.id, role_id=role.id, assigned_by_id=invited_by))
        link = await self._identity.password_setup_link(
            email, f"{self._settings.app_base_url.rstrip('/')}/login"
        )
        await self._audit.record(
            action="auth.invited",
            entity_type="user",
            entity_id=user.id,
            actor_user_id=invited_by,
            context={"role": role_key},
        )
        return Invitation(user=user, link=link)

    # ------------------------------------------------------------ helpers

    async def _audit_auth(
        self,
        action: str,
        user_id: uuid.UUID | None,
        meta: RequestMeta,
        **context: object,
    ) -> None:
        await self._audit.record(
            action=action,
            entity_type="user",
            entity_id=user_id,
            actor_user_id=user_id,
            context=context,
            ip=meta.ip,
            user_agent=meta.user_agent,
        )
