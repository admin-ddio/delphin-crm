"""Needs PostgreSQL. The session fixture has already round-tripped the migrations."""

from __future__ import annotations

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.health import ALEMBIC_INI
from app.core.request_id import _request_id
from app.main import create_app
from app.platform.activity.service import ActivityRecorder
from app.platform.audit.models import AuditLog
from app.platform.audit.service import REDACTED, AuditWriter
from app.platform.identity.models import User
from app.platform.system.counters import next_value
from tests.conftest import make_settings

pytestmark = pytest.mark.integration


async def test_at_head(db_session: AsyncSession) -> None:
    heads = set(ScriptDirectory.from_config(Config(str(ALEMBIC_INI))).get_heads())
    current = set(
        (await db_session.execute(text("SELECT version_num FROM alembic_version"))).scalars().all()
    )
    assert current == heads


async def test_extensions_installed(db_session: AsyncSession) -> None:
    installed = set(
        (await db_session.execute(text("SELECT extname FROM pg_extension"))).scalars().all()
    )
    assert {"pgcrypto", "citext", "pg_trgm"} <= installed


async def test_audit_log_is_append_only(db_session: AsyncSession) -> None:
    token = _request_id.set("integration-test-1")
    try:
        entry = await AuditWriter(db_session).record(
            action="test.created",
            entity_type="test",
            entity_id="1",
            changes={"name": "x", "password": "hunter2"},
            user_agent="ua" * 400,
        )
    finally:
        _request_id.reset(token)
    result = await db_session.execute(select(AuditLog).where(AuditLog.id == entry.id))
    stored = result.scalar_one()
    assert stored.changes == {"name": "x", "password": REDACTED}
    assert stored.request_id == "integration-test-1"
    assert stored.user_agent is not None
    assert len(stored.user_agent) == 500

    for statement in (
        "UPDATE audit_log SET action = 'tampered'",
        "DELETE FROM audit_log",
        "TRUNCATE audit_log",
    ):
        with pytest.raises(DBAPIError, match="append-only"):
            async with db_session.begin_nested():
                await db_session.execute(text(statement))


async def test_email_unique_case_insensitive(db_session: AsyncSession) -> None:
    db_session.add(User(email="Person@Example.test", full_name="A"))
    await db_session.flush()
    savepoint = await db_session.begin_nested()
    db_session.add(User(email="person@example.TEST", full_name="B"))
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await savepoint.rollback()


async def test_counters_increment(db_session: AsyncSession) -> None:
    assert await next_value(db_session, "test-counter") == 1
    assert await next_value(db_session, "test-counter") == 2
    assert await next_value(db_session, "other-counter") == 1


async def test_activity_recorder(db_session: AsyncSession) -> None:
    event = await ActivityRecorder(db_session).record(
        verb="created", subject_type="test", subject_id="1", context={"token": "t"}
    )
    assert event.id is not None
    assert event.context == {"token": REDACTED}


def test_readyz_reports_ready(migrated_database_url: str) -> None:
    app = create_app(make_settings(database_url=migrated_database_url))
    with TestClient(app) as client:
        response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {"database": True, "migrations": True}}


def test_readyz_reports_unavailable_without_db() -> None:
    app = create_app(
        make_settings(database_url="postgresql+asyncpg://nobody:nothing@127.0.0.1:1/none")
    )
    with TestClient(app) as client:
        response = client.get("/readyz")
    assert response.status_code == 503
    assert response.json()["checks"]["database"] is False
