"""HTTP surface of the reports module. CSV export is a stub slot."""

from __future__ import annotations

from fastapi import APIRouter

from app.authz.dependencies import CurrentActor
from app.core.errors import AUTH_ERROR_RESPONSES, NOT_PORTED_RESPONSE, NotImplementedYet

TAG = {"name": "reports", "description": "Reports and CSV export"}

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/export.csv", responses={**AUTH_ERROR_RESPONSES, **NOT_PORTED_RESPONSE})
async def export_csv(actor: CurrentActor) -> None:
    raise NotImplementedYet
