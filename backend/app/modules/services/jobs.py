"""Background jobs of the services module (registered on import; see scripts/run_jobs.py)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import Clock
from app.modules.services.service import ServicesService
from app.platform.jobs.interfaces import registry


class GenerateMonthly:
    """Create this month's retainer tasks (idempotent: safe to run daily)."""

    name = "services.generate_monthly"

    async def run(self, session: AsyncSession, clock: Clock) -> Mapping[str, Any]:
        return await ServicesService(session, clock=clock).generate_all()


registry.register(GenerateMonthly())
