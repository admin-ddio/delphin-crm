"""Background jobs of the onboarding module (registered on import; see scripts/run_jobs.py)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import Clock
from app.core.config import get_settings
from app.modules.onboarding.service import OnboardingService
from app.platform.jobs.interfaces import registry


class OverdueReminders:
    """Notify Account Managers about overdue onboarding steps (run daily)."""

    name = "onboarding.overdue_reminders"

    async def run(self, session: AsyncSession, clock: Clock) -> Mapping[str, Any]:
        service = OnboardingService(session, clock=clock, settings=get_settings())
        return await service.remind_overdue()


registry.register(OverdueReminders())
