"""Run due background jobs once (alternative to POST /api/v1/jobs/run for a host cron).

STUB: no jobs are registered until features are ported; exits 0 after listing them.
"""

from __future__ import annotations

import sys

from app.platform.jobs.interfaces import registry


def main() -> int:
    if not len(registry):
        print("no jobs registered (jobs are ported with their features)")
        return 0
    print("registered jobs:", ", ".join(registry.names()))
    print("job execution lands with the jobs module port", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
