"""Shared column types. Money is NUMERIC(14,2) plus an ISO 4217 currency; never float."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import DateTime, Dialect, Numeric, String
from sqlalchemy.types import TypeDecorator

Money = Numeric(14, 2, asdecimal=True)
CurrencyCode = String(3)

MONEY_QUANTUM = Decimal("0.01")


def to_money(value: Decimal | int | str) -> Decimal:
    """Normalise to two decimal places, half-up.

    The clickable demo rounds invoice totals and payments half-up to 2 dp.
    TODO(pilot-port): confirm against services/finance.ts.
    """
    return Decimal(value).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


class UTCDateTime(TypeDecorator[datetime]):
    """timestamptz that refuses naive datetimes and always returns UTC."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            msg = "Naive datetime rejected: store timezone-aware UTC values"
            raise ValueError(msg)
        return value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        return value.astimezone(UTC) if value is not None else None
