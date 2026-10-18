"""EmailSender interface and a development sender that only logs metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class EmailMessage:
    to: tuple[str, ...]
    subject: str
    text_body: str
    html_body: str | None = None
    reply_to: str | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)


class EmailSender(Protocol):
    async def send(self, message: EmailMessage) -> None: ...


class LoggingEmailSender:
    """Development sender. Logs recipients and subject; never the body, which may hold tokens."""

    async def send(self, message: EmailMessage) -> None:
        logger.info("email_not_sent", to=list(message.to), subject=message.subject)
