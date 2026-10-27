"""Dates for service tasks. Pure.

Clickable demo: recurring monthly tasks fall on a day of the month; due dates move
off weekends (Saturday +2, Sunday +1); a period is identified as YYYY-MM.
"""

from __future__ import annotations

from datetime import date, timedelta

SATURDAY = 5
SUNDAY = 6


def off_weekend(day: date) -> date:
    if day.weekday() == SATURDAY:
        return day + timedelta(days=2)
    if day.weekday() == SUNDAY:
        return day + timedelta(days=1)
    return day


def period_key(day: date) -> str:
    return f"{day.year:04d}-{day.month:02d}"


def monthly_due(period: date, day_of_month: int) -> date:
    """Due date of a monthly task in the period's month (days are 1–28, always valid)."""
    return off_weekend(period.replace(day=day_of_month))


def phase_due(start: date, start_offset_days: int, duration_days: int) -> date:
    """Due date of a setup or delivery task, counted from the service's start."""
    return off_weekend(start + timedelta(days=start_offset_days + duration_days))
