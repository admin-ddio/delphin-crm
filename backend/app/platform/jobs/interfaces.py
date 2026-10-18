"""Job interface and registry. Modules register jobs; the jobs module runs them.

Jobs must be idempotent per period (e.g. recurring task generation keys each
occurrence; see modules/services/PARITY.md).
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import Clock


class Job(Protocol):
    name: str

    async def run(self, session: AsyncSession, clock: Clock) -> Mapping[str, Any]:
        """Do one run; return a JSON-serialisable summary stored in job_runs.result."""
        ...


class JobRegistry:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}

    def register(self, job: Job) -> Job:
        if job.name in self._jobs:
            msg = f"Job already registered: {job.name}"
            raise ValueError(msg)
        self._jobs[job.name] = job
        return job

    def get(self, name: str) -> Job:
        return self._jobs[name]

    def names(self) -> list[str]:
        return sorted(self._jobs)

    def __iter__(self) -> Iterator[Job]:
        return iter(self._jobs[name] for name in self.names())

    def __len__(self) -> int:
        return len(self._jobs)


registry = JobRegistry()
