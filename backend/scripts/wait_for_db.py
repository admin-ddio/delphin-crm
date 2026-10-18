"""Block until PostgreSQL accepts connections (used by the migrate service)."""

from __future__ import annotations

import asyncio
import os
import sys
import time

import asyncpg

TIMEOUT_SECONDS = float(os.environ.get("DB_WAIT_TIMEOUT", "60"))


async def main() -> int:
    url = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    deadline = time.monotonic() + TIMEOUT_SECONDS
    attempt = 0
    while True:
        attempt += 1
        try:
            conn = await asyncpg.connect(url, timeout=5)
        except (OSError, asyncpg.PostgresError) as exc:
            if time.monotonic() > deadline:
                print(f"database not ready after {attempt} attempts: {exc!r}", file=sys.stderr)
                return 1
            await asyncio.sleep(1)
        else:
            await conn.close()
            print(f"database ready after {attempt} attempt(s)")
            return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
