"""Idempotently add the default roles from app.authz.permissions that are missing.

Configuration only: no users, clients or metrics are ever seeded.
Run: make seed-config
"""

from __future__ import annotations

import asyncio
import os
import sys

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import create_async_engine

from app.authz.permissions import DEFAULT_ROLES, is_catalogue_ported
from app.platform.identity.models import Role


async def main() -> int:
    if not is_catalogue_ported():
        print(
            "warning: using the interim permission catalogue from the clickable demo; "
            "replace it with the pilot's permissions.ts.",
            file=sys.stderr,
        )
    engine = create_async_engine(os.environ["DATABASE_URL"])
    async with engine.begin() as conn:
        for role in DEFAULT_ROLES:
            stmt = insert(Role).values(
                key=role.key,
                name=role.name,
                description=role.description or None,
                permissions=sorted(role.permissions),
                is_system=True,
            )
            # Never overwrite an existing role: admins edit permissions in the app
            # (Organization & Role Settings); permission changes ship as migrations.
            stmt = stmt.on_conflict_do_nothing(index_elements=[Role.key])
            await conn.execute(stmt)
    await engine.dispose()
    print(f"seeded {len(DEFAULT_ROLES)} roles")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
