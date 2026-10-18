"""HTTP surface of the jobs module: the external cron trigger.

Bearer-token auth (CRON_SECRET) is live; running jobs is a stub until ported.
The path is exempt from the CSRF check because it is not cookie-authenticated.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header

from app.core.config import Settings, get_app_settings
from app.core.errors import NOT_PORTED_RESPONSE, ErrorEnvelope, NotImplementedYet, Unauthorized
from app.core.security import tokens_match

TAG = {"name": "jobs", "description": "Scheduled job runner (bearer CRON_SECRET)"}

RUN_PATH = "/api/v1/jobs/run"

router = APIRouter(prefix="/jobs", tags=["jobs"])


async def require_cron_secret(
    settings: Annotated[Settings, Depends(get_app_settings)],
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise Unauthorized
    if not tokens_match(settings.cron_secret.get_secret_value(), token):
        raise Unauthorized


@router.post(
    "/run",
    dependencies=[Depends(require_cron_secret)],
    responses={401: {"model": ErrorEnvelope}, **NOT_PORTED_RESPONSE},
)
async def run_due_jobs() -> None:
    raise NotImplementedYet
