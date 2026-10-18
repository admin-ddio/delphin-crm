"""/healthz (liveness: process is up) and /readyz (DB reachable, migrations at head)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.logging import get_logger

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"
logger = get_logger(__name__)

router = APIRouter(tags=["health"])


@lru_cache(maxsize=1)
def expected_heads() -> frozenset[str]:
    script = ScriptDirectory.from_config(Config(str(ALEMBIC_INI)))
    return frozenset(script.get_heads())


async def database_revisions(engine: AsyncEngine) -> frozenset[str]:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
        rows = await conn.execute(text("SELECT version_num FROM alembic_version"))
        return frozenset(rows.scalars().all())


@router.get("/healthz", operation_id="health_liveness")
async def liveness() -> dict[str, str]:
    return {"status": "ok"}


@router.get(
    "/readyz",
    operation_id="health_readiness",
    responses={503: {"description": "Database unreachable or migrations not at head"}},
)
async def readiness(request: Request) -> JSONResponse:
    checks: dict[str, Any] = {"database": False, "migrations": False}
    try:
        current = await database_revisions(request.app.state.engine)
        checks["database"] = True
        checks["migrations"] = current == expected_heads()
    except Exception as exc:  # any failure means "not ready"
        logger.warning("readiness_check_failed", exc_type=type(exc).__name__)
    ready = all(checks.values())
    return JSONResponse(
        status_code=200 if ready else 503,
        content={"status": "ok" if ready else "unavailable", "checks": checks},
    )
