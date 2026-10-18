"""Platform helpers that need no database: redaction, counters formatting, jobs, e-mail."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import Clock
from app.platform.audit.service import REDACTED, is_secret_key, redact
from app.platform.email.interfaces import EmailMessage, LoggingEmailSender
from app.platform.jobs.interfaces import JobRegistry
from app.platform.system.counters import format_code


@pytest.mark.parametrize(
    "key",
    [
        "password",
        "newPassword",
        "api_key",
        "API-Key",
        "apiKey",
        "access_token",
        "Authorization",
        "client_secret",
        "Cookie",
        "privateKey",
        "session_id",
        "credentials",
    ],
)
def test_secret_keys_detected(key: str) -> None:
    assert is_secret_key(key)


@pytest.mark.parametrize("key", ["name", "email", "status", "domain", "shipping", "amount"])
def test_ordinary_keys_kept(key: str) -> None:
    assert not is_secret_key(key)


def test_redact_is_deep_and_non_mutating() -> None:
    original = {
        "name": "Acme",
        "password": "hunter2",
        "nested": {"api_key": "k", "list": [{"token": "t", "ok": 1}, "plain"]},
        "tuple": ({"secret": "s"},),
    }
    result = redact(original)
    assert result == {
        "name": "Acme",
        "password": REDACTED,
        "nested": {"api_key": REDACTED, "list": [{"token": REDACTED, "ok": 1}, "plain"]},
        "tuple": [{"secret": REDACTED}],
    }
    assert original["password"] == "hunter2"


def test_format_code() -> None:
    assert format_code("CL", 1) == "CL-0001"
    assert format_code("INV-2026", 12) == "INV-2026-0012"
    assert format_code("PRJ", 12345) == "PRJ-12345"


class _NoopJob:
    name = "noop"

    async def run(self, session: AsyncSession, clock: Clock) -> Mapping[str, Any]:
        return {}


def test_job_registry() -> None:
    registry = JobRegistry()
    job = _NoopJob()
    registry.register(job)
    assert registry.names() == ["noop"]
    assert registry.get("noop") is job
    assert list(registry) == [job]
    assert len(registry) == 1
    with pytest.raises(ValueError, match="already registered"):
        registry.register(_NoopJob())


async def test_logging_email_sender_never_raises() -> None:
    await LoggingEmailSender().send(
        EmailMessage(to=("a@example.test",), subject="Hi", text_body="link with token")
    )
