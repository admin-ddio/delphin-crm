"""Gap-free human codes from the counters table, safe under concurrency.

The upsert takes a row lock on the counter, so concurrent transactions serialise
on the same key and a rollback releases the number without a gap being consumed
by someone else's committed row.
"""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.system.models import Counter


async def next_value(session: AsyncSession, key: str) -> int:
    stmt = (
        insert(Counter)
        .values(key=key, value=1)
        .on_conflict_do_update(
            index_elements=[Counter.key],
            set_={"value": Counter.value + 1, "updated_at": func.now()},
        )
        .returning(Counter.value)
    )
    return int((await session.execute(stmt)).scalar_one())


def format_code(prefix: str, value: int, *, width: int = 4) -> str:
    """format_code("CL", 1) -> "CL-0001"; format_code("INV-2026", 7) -> "INV-2026-0007"."""
    return f"{prefix}-{value:0{width}d}"
