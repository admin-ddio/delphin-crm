"""Idempotency-Key header for POST endpoints that create records.

The scaffold validates and exposes the header. Replay storage (key -> response)
is deliberately not built yet: it lands with the first module whose create
endpoint needs it, with its own table and migration.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Header

IDEMPOTENCY_HEADER = "Idempotency-Key"

IdempotencyKey = Annotated[
    str | None,
    Header(
        alias=IDEMPOTENCY_HEADER,
        min_length=8,
        max_length=128,
        pattern=r"^[A-Za-z0-9._:-]+$",
        description="Client-generated key; repeating a POST with the same key is a no-op.",
    ),
]
