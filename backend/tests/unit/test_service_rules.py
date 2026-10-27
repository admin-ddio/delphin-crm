"""Pure rules of the services module: dates and the onboarding checklist per service."""

from __future__ import annotations

from datetime import UTC, date, datetime

from app.core.clock import FixedClock, business_today
from app.modules.services.catalogue import access_items_for
from app.modules.services.scheduling import monthly_due, off_weekend, period_key, phase_due


def test_due_dates_move_off_weekends() -> None:
    assert off_weekend(date(2026, 10, 24)) == date(2026, 10, 26)  # Saturday → Monday
    assert off_weekend(date(2026, 10, 25)) == date(2026, 10, 26)  # Sunday → Monday
    assert off_weekend(date(2026, 10, 27)) == date(2026, 10, 27)  # Tuesday stays


def test_monthly_and_phase_dates() -> None:
    assert period_key(date(2026, 3, 31)) == "2026-03"
    assert monthly_due(date(2026, 11, 1), 1) == date(2026, 11, 2)  # 1 Nov 2026 is a Sunday
    assert monthly_due(date(2026, 11, 1), 4) == date(2026, 11, 4)
    assert phase_due(date(2026, 3, 2), 0, 5) == date(2026, 3, 9)  # 7 Mar is a Saturday


def test_access_items_are_the_union_of_the_services() -> None:
    seo = [key for key, _, _ in access_items_for(["seo"])]
    assert seo == ["GSC", "GA4", "CMS", "AHREFS", "GDRIVE"]
    both = [key for key, _, _ in access_items_for(["seo", "website"])]
    assert both == ["GSC", "GA4", "CMS", "AHREFS", "DOMAIN_DNS", "HOSTING", "GDRIVE"]
    assert [key for key, _, _ in access_items_for([])] == ["GDRIVE"]


def test_business_today_is_india_time() -> None:
    # 20:00 UTC on 27 Oct is already 01:30 on 28 Oct in India.
    assert business_today(FixedClock(datetime(2026, 10, 27, 20, 0, tzinfo=UTC))) == date(
        2026, 10, 28
    )
    assert business_today(FixedClock(datetime(2026, 10, 27, 10, 0, tzinfo=UTC))) == date(
        2026, 10, 27
    )
