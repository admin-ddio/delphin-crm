"""FastAPI dependencies: get_actor, require_permission, require_any.

Session resolution (cookie -> Actor) is the ActorResolver interface; the default
is the sessions-table resolver. Tests may override get_actor_resolver or get_actor.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Annotated, Protocol

import structlog
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.actor import Actor
from app.authz.permissions import validate_permission
from app.core.clock import Clock, get_clock
from app.core.config import Settings, get_app_settings
from app.core.errors import Forbidden, Unauthorized
from app.db.session import get_session
from app.platform.identity.sessions import DbActorResolver


class ActorResolver(Protocol):
    async def resolve(self, session: AsyncSession, token: str) -> Actor | None:
        """Return the Actor for a raw session token, or None if invalid/expired/revoked."""
        ...


def get_actor_resolver(clock: Annotated[Clock, Depends(get_clock)]) -> ActorResolver:
    return DbActorResolver(clock)


async def get_actor(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    resolver: Annotated[ActorResolver, Depends(get_actor_resolver)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> Actor:
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise Unauthorized
    actor = await resolver.resolve(session, token)
    if actor is None:
        raise Unauthorized
    structlog.contextvars.bind_contextvars(user_id=str(actor.user_id))
    return actor


CurrentActor = Annotated[Actor, Depends(get_actor)]


def require_permission(permission: str) -> Callable[[Actor], Awaitable[Actor]]:
    """Dependency factory: 403 unless the actor holds `permission` (or `*`)."""
    validate_permission(permission)

    async def dependency(actor: CurrentActor) -> Actor:
        if not actor.can(permission):
            raise Forbidden(details={"permission": permission})
        return actor

    return dependency


def require_any(*permissions: str) -> Callable[[Actor], Awaitable[Actor]]:
    """Dependency factory: 403 unless the actor holds at least one of `permissions`."""
    if not permissions:
        msg = "require_any() needs at least one permission"
        raise ValueError(msg)
    for permission in permissions:
        validate_permission(permission)

    async def dependency(actor: CurrentActor) -> Actor:
        if not actor.can_any(*permissions):
            raise Forbidden(details={"any_of": list(permissions)})
        return actor

    return dependency
