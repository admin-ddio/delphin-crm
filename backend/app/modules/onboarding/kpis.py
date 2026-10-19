"""KPI progress and status (On track / At risk / Behind), from the product mockups. Pure.

progress = how far the current value has moved from baseline towards target (0–100,
works for "lower is better" targets too). Status compares it with the share of the
timeline already elapsed (start → target date):
  achieved      progress ≥ 100
  on_track      progress ≥ expected − 5
  at_risk       progress ≥ expected − 20
  behind        otherwise
  not_measured  no current value yet
TODO(confirm): thresholds with the account team.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Final, Literal

KpiStatus = Literal["not_measured", "on_track", "at_risk", "behind", "achieved"]
ON_TRACK_SLACK: Final = 5
AT_RISK_SLACK: Final = 20


def progress(baseline: Decimal, target: Decimal, current: Decimal | None) -> int | None:
    if current is None:
        return None
    span = target - baseline
    if span == 0:
        return 100 if current == target else 0
    pct = (current - baseline) / span * 100
    return int(max(Decimal(0), min(Decimal(100), pct)).to_integral_value())


def expected(start: date, target_date: date | None, today: date) -> int:
    """Share of the timeline elapsed (0–100); 0 without a target date."""
    if target_date is None or target_date <= start:
        return 0 if target_date is None else 100
    elapsed = (min(today, target_date) - start).days
    return max(0, min(100, round(elapsed / (target_date - start).days * 100)))


def status(pct: int | None, start: date, target_date: date | None, today: date) -> KpiStatus:
    if pct is None:
        return "not_measured"
    if pct >= 100:
        return "achieved"
    due = expected(start, target_date, today)
    if pct >= due - ON_TRACK_SLACK:
        return "on_track"
    if pct >= due - AT_RISK_SLACK:
        return "at_risk"
    return "behind"
