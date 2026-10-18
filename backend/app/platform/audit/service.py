"""Write audit entries. Secret-looking keys are redacted before anything is stored."""

from __future__ import annotations

import re
import uuid
from collections.abc import Mapping
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.request_id import get_request_id
from app.platform.audit.models import AuditLog

REDACTED = "[REDACTED]"

# Matched against the key with everything but letters and digits removed, lowercased,
# so "api_key", "API-Key" and "apiKey" all match "apikey".
_SECRET_FRAGMENTS = (
    "password",
    "passwd",
    "secret",
    "token",
    "apikey",
    "authorization",
    "cookie",
    "credential",
    "privatekey",
    "sessionid",
    "signature",
)
_NON_ALNUM = re.compile(r"[^a-z0-9]")


def is_secret_key(key: str) -> bool:
    normalised = _NON_ALNUM.sub("", key.lower())
    return any(fragment in normalised for fragment in _SECRET_FRAGMENTS)


def redact(value: Any) -> Any:
    """Return a deep copy of value with every secret-looking key's value replaced."""
    if isinstance(value, Mapping):
        return {
            str(key): REDACTED if is_secret_key(str(key)) else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list | tuple):
        return [redact(item) for item in value]
    return value


class AuditWriter:
    """Append entries to audit_log inside the caller's transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(
        self,
        *,
        action: str,
        entity_type: str,
        entity_id: str | uuid.UUID | None = None,
        actor_user_id: uuid.UUID | None = None,
        changes: Mapping[str, Any] | None = None,
        context: Mapping[str, Any] | None = None,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> AuditLog:
        entry = AuditLog(
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            actor_user_id=actor_user_id,
            changes=redact(dict(changes or {})),
            context=redact(dict(context or {})),
            request_id=get_request_id(),
            ip=ip,
            user_agent=user_agent[:500] if user_agent else None,
        )
        self._session.add(entry)
        await self._session.flush()
        return entry
