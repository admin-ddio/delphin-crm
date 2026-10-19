"""Run every registered background job once (for a host cron / scheduler).

Each job runs in its own transaction and is recorded in job_runs. Jobs must be
idempotent per period (e.g. reminders are sent at most once a day).
Run: docker compose run --rm -T backend python scripts/run_jobs.py [job-name …]
"""

from __future__ import annotations

import asyncio
import importlib
import os
import pkgutil
import sys
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.modules
from app.core.clock import SystemClock
from app.db.discovery import import_all_models
from app.platform.jobs.interfaces import registry
from app.platform.jobs.models import JobRun


def load_jobs() -> None:
    """Import every app.modules.<module>.jobs so jobs register themselves."""
    for module in pkgutil.iter_modules(app.modules.__path__):
        if importlib.util.find_spec(f"app.modules.{module.name}.jobs"):
            importlib.import_module(f"app.modules.{module.name}.jobs")


async def main(names: list[str]) -> int:
    import_all_models()
    load_jobs()
    if not len(registry):
        print("no jobs registered")
        return 0
    wanted = names or registry.names()
    unknown = set(wanted) - set(registry.names())
    if unknown:
        print(f"unknown jobs: {', '.join(sorted(unknown))}", file=sys.stderr)
        return 2
    engine = create_async_engine(os.environ["DATABASE_URL"])
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    failed = 0
    for name in wanted:
        async with sessions() as session:
            run = JobRun(job_name=name, status="running", triggered_by="cron")
            try:
                async with session.begin():
                    result = await registry.get(name).run(session, SystemClock())
                    session.add(run)
                    run.status, run.result = "succeeded", dict(result)
                    run.finished_at = datetime.now(UTC)
                print(f"{name}: {dict(result)}")
            except Exception as exc:  # record and continue with the next job
                failed += 1
                print(f"{name}: failed: {exc}", file=sys.stderr)
    await engine.dispose()
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
