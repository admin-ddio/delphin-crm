"""HTTP surface of the documents module.

`files_router` holds the GET /api/v1/files/{file_id} slot. It requires an
authenticated actor on every request (no public file URLs). The per-document
access check lands with the port.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.authz.dependencies import CurrentActor
from app.core.errors import AUTH_ERROR_RESPONSES, NOT_PORTED_RESPONSE, NotImplementedYet

TAG = {"name": "documents", "description": "Documents and access-checked file downloads"}

router = APIRouter(prefix="/documents", tags=["documents"])
files_router = APIRouter(prefix="/files", tags=["documents"])


@files_router.get("/{file_id}", responses={**AUTH_ERROR_RESPONSES, **NOT_PORTED_RESPONSE})
async def download_file(file_id: UUID, actor: CurrentActor) -> None:
    raise NotImplementedYet
