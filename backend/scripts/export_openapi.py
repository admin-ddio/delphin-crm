"""Print the OpenAPI document to stdout without starting a server or touching the DB.

Used by `make gen-api` to regenerate frontend/src/api/schema.d.ts.
"""

from __future__ import annotations

import json
import sys

from pydantic import SecretStr

from app.core.config import Settings
from app.main import create_app


def main() -> int:
    settings = Settings(
        app_env="development",
        database_url="postgresql+asyncpg://openapi:openapi@localhost:5432/openapi",
        secret_key=SecretStr("openapi-export-only"),  # never used to sign anything
        cron_secret=SecretStr("openapi-export-only"),
        firebase_project_id="demo-openapi-export",
        log_level="WARNING",
    )
    app = create_app(settings)
    json.dump(app.openapi(), sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
