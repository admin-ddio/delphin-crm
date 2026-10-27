"""Injectable time source. Services take a Clock; they never call datetime.now() directly."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, timezone
from typing import Final, Protocol

#: Delphin works in India Standard Time (UTC+05:30, no daylight saving). Calendar
#: dates people pick (effective dates, service starts, monthly periods) use it.
BUSINESS_TZ: Final = timezone(timedelta(hours=5, minutes=30), "IST")


class Clock(Protocol):
    def now(self) -> datetime:
        """Current time, timezone-aware, in UTC."""
        ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


@dataclass
class FixedClock:
    """Deterministic clock for tests."""

    current: datetime

    def __post_init__(self) -> None:
        if self.current.tzinfo is None:
            msg = "FixedClock needs a timezone-aware datetime"
            raise ValueError(msg)

    def now(self) -> datetime:
        return self.current

    def advance(self, delta: timedelta) -> None:
        self.current = self.current + delta


def business_today(clock: Clock) -> date:
    """Today's date in the business time zone (not the UTC date)."""
    return clock.now().astimezone(BUSINESS_TZ).date()


def get_clock() -> Clock:
    """FastAPI dependency; override in tests with a FixedClock."""
    return SystemClock()
