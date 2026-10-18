"""Notification delivery boundary. The notifications module implements it when ported."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class NotificationRequest:
    user_id: uuid.UUID
    kind: str
    title: str
    body: str | None = None
    link: str | None = None
    entity_type: str | None = None
    entity_id: str | None = None


class Notifier(Protocol):
    async def notify(self, request: NotificationRequest) -> None:
        """Persist the in-app notification and fan out to enabled channels."""
        ...
