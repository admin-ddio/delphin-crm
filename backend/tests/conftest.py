"""Shared fixtures.

Unit and contract tests need no database: the app's engine is created lazily and
never connects. Integration tests (marked `integration`) use TEST_DATABASE_URL:

- once per session, the test DB is created if missing and migrations are
  round-tripped (upgrade head -> downgrade base -> upgrade head);
- each test runs inside a transaction that is rolled back afterwards.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import asyncpg
import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import Settings
from app.main import create_app

BACKEND_DIR = Path(__file__).resolve().parents[1]
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


def make_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": "test",
        "database_url": TEST_DATABASE_URL
        or "postgresql+asyncpg://unused:unused@localhost:5432/unused",
        "secret_key": SecretStr("test-secret-key-0123456789abcdef0123456789"),
        "cron_secret": SecretStr("test-cron-secret-0123456789abcdef012345678"),
        "firebase_project_id": os.environ.get("FIREBASE_PROJECT_ID", "demo-delphin"),
        "firebase_auth_emulator_host": "",
        "allowed_hosts": ["testserver", "localhost"],
        "log_level": "WARNING",
    }
    values.update(overrides)
    return Settings.model_validate(values)


@pytest.fixture
def settings() -> Settings:
    return make_settings()


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


# ---------------------------------------------------------------- integration


def _alembic_config(url: str) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.attributes["database_url"] = url
    config.attributes["skip_logging_config"] = True
    return config


def _admin_dsn(url: str) -> tuple[str, str]:
    """(DSN of the maintenance DB, name of the test DB) for an asyncpg URL."""
    parts = urlsplit(url.replace("postgresql+asyncpg://", "postgresql://", 1))
    db_name = parts.path.lstrip("/")
    return urlunsplit(parts._replace(path="/postgres")), db_name


async def _ensure_database(url: str) -> None:
    dsn, db_name = _admin_dsn(url)
    conn = await asyncpg.connect(dsn)
    try:
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", db_name)
        if not exists:
            await conn.execute(f'CREATE DATABASE "{db_name}"')
    finally:
        await conn.close()


@pytest.fixture(scope="session")
def migrated_database_url() -> str:
    if not TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL not set (run via `make test`)")
    asyncio.run(_ensure_database(TEST_DATABASE_URL))
    config = _alembic_config(TEST_DATABASE_URL)
    # Definition of Done: the baseline must round-trip cleanly.
    command.upgrade(config, "head")
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    return TEST_DATABASE_URL


@pytest.fixture
async def db_session(migrated_database_url: str) -> AsyncIterator[AsyncSession]:
    """A session whose work is rolled back after the test, even if it committed."""
    engine = create_async_engine(migrated_database_url, poolclass=NullPool)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()
    await engine.dispose()
