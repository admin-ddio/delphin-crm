"""Identity provider boundary, implemented with Firebase Auth (ADR-0009).

Firebase owns credentials (passwords, e-mail verification, reset e-mails,
brute-force throttling). The app owns authorisation: who is invited, roles,
server-side sessions and the audit log. The only thing that crosses the boundary
is a verified identity: uid, e-mail and whether that e-mail is verified.

The Admin SDK is synchronous, so calls run in a worker thread. With
FIREBASE_AUTH_EMULATOR_HOST set, the SDK talks to the local emulator and needs
no credentials; otherwise every call, ID-token verification included, needs
GOOGLE_APPLICATION_CREDENTIALS (firebase-admin 7 builds its client from them).
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated, Any, Protocol

import firebase_admin
from fastapi import Depends
from firebase_admin import auth as firebase_auth

from app.core.config import Settings, get_app_settings


@dataclass(frozen=True, slots=True)
class IdentityClaims:
    uid: str
    email: str | None
    email_verified: bool
    name: str | None = None


class InvalidIdentityTokenError(Exception):
    """The ID token is malformed, expired, for another project or otherwise unverifiable."""


class IdentityProvider(Protocol):
    async def verify_id_token(self, id_token: str) -> IdentityClaims: ...

    async def ensure_user(self, email: str, display_name: str) -> str:
        """Return the uid for `email`, creating a password-less account if needed."""
        ...

    async def password_setup_link(self, email: str, continue_url: str) -> str:
        """A one-time link that lets the user choose (or reset) their password."""
        ...

    async def email_verified(self, uid: str) -> bool | None:
        """Whether the account's e-mail is verified; None if the account doesn't exist."""
        ...

    async def delete_user(self, uid: str) -> None:
        """Delete the identity (no error if it is already gone)."""
        ...


class FirebaseIdentityProvider:
    def __init__(self, project_id: str) -> None:
        self._app = firebase_app(project_id)

    async def verify_id_token(self, id_token: str) -> IdentityClaims:
        try:
            decoded: dict[str, Any] = await asyncio.to_thread(
                firebase_auth.verify_id_token, id_token, app=self._app
            )
        except (
            ValueError,
            firebase_auth.InvalidIdTokenError,
            firebase_auth.CertificateFetchError,
        ) as exc:
            raise InvalidIdentityTokenError(str(exc)) from exc
        return IdentityClaims(
            uid=str(decoded["uid"]),
            email=decoded.get("email"),
            email_verified=bool(decoded.get("email_verified", False)),
            name=decoded.get("name"),
        )

    async def ensure_user(self, email: str, display_name: str) -> str:
        def _ensure() -> str:
            try:
                return str(firebase_auth.get_user_by_email(email, app=self._app).uid)
            except firebase_auth.UserNotFoundError:
                record = firebase_auth.create_user(
                    email=email, display_name=display_name, email_verified=False, app=self._app
                )
                return str(record.uid)

        return await asyncio.to_thread(_ensure)

    async def password_setup_link(self, email: str, continue_url: str) -> str:
        settings = firebase_auth.ActionCodeSettings(url=continue_url)
        link: str = await asyncio.to_thread(
            firebase_auth.generate_password_reset_link, email, settings, app=self._app
        )
        return link

    async def email_verified(self, uid: str) -> bool | None:
        def _lookup() -> bool | None:
            try:
                return bool(firebase_auth.get_user(uid, app=self._app).email_verified)
            except firebase_auth.UserNotFoundError:
                return None

        return await asyncio.to_thread(_lookup)

    async def delete_user(self, uid: str) -> None:
        def _delete() -> None:
            with contextlib.suppress(firebase_auth.UserNotFoundError):
                firebase_auth.delete_user(uid, app=self._app)

        await asyncio.to_thread(_delete)


@lru_cache(maxsize=4)
def firebase_app(project_id: str) -> firebase_admin.App:
    """One named Admin SDK app per project (credentials resolved lazily by the SDK)."""
    name = f"delphin-{project_id}"
    try:
        return firebase_admin.get_app(name)
    except ValueError:
        return firebase_admin.initialize_app(options={"projectId": project_id}, name=name)


def get_identity_provider(
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> IdentityProvider:
    """FastAPI dependency; tests override it with a fake."""
    return FirebaseIdentityProvider(settings.firebase_project_id)
