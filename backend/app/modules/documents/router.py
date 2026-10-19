"""HTTP surface of the documents module.

Client documents live under /documents/…; files are downloaded only through
GET /api/v1/files/{id}, which re-checks access on every request (no public URLs)
and always serves an attachment.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.dependencies import CurrentActor
from app.core.config import Settings, get_app_settings
from app.core.errors import AUTH_ERROR_RESPONSES, ErrorEnvelope
from app.db.session import get_session
from app.modules.documents.schemas import ClientDocuments, DocumentOut, DocumentUpdate, FolderIn
from app.modules.documents.service import DocumentService
from app.platform.storage.interfaces import StorageBackend
from app.platform.storage.local import get_storage

TAG = {"name": "documents", "description": "Documents and access-checked file downloads"}

router = APIRouter(prefix="/documents", tags=["documents"])
files_router = APIRouter(prefix="/files", tags=["documents"])

ERRORS: dict[int | str, dict[str, Any]] = {
    **AUTH_ERROR_RESPONSES,
    404: {"model": ErrorEnvelope, "description": "Not found, or outside your access"},
    409: {"model": ErrorEnvelope, "description": "Duplicate folder name"},
    422: {"model": ErrorEnvelope, "description": "File type/size or business rule"},
}


def get_document_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: Annotated[StorageBackend, Depends(get_storage)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> DocumentService:
    return DocumentService(session, storage=storage, settings=settings)


Service = Annotated[DocumentService, Depends(get_document_service)]


@router.get("/clients/{client_id}", response_model=ClientDocuments, responses=ERRORS)
async def client_documents(
    client_id: uuid.UUID, actor: CurrentActor, service: Service
) -> ClientDocuments:
    """Folders (with counts), every document, and what the actor may do."""
    return await service.for_client(actor, client_id)


@router.post(
    "/clients/{client_id}",
    status_code=status.HTTP_201_CREATED,
    response_model=DocumentOut,
    responses=ERRORS,
)
async def upload_document(
    *,
    client_id: uuid.UUID,
    actor: CurrentActor,
    service: Service,
    settings: Annotated[Settings, Depends(get_app_settings)],
    file: Annotated[UploadFile, File()],
    folder_id: Annotated[uuid.UUID | None, Form()] = None,
    folder: Annotated[str | None, Form(max_length=60, description="Folder name")] = None,
    description: Annotated[str | None, Form(max_length=500)] = None,
) -> DocumentOut:
    """Multipart upload (≤ MAX_UPLOAD_BYTES). Pick the folder by id or by name."""
    data = await file.read(settings.max_upload_bytes + 1)
    return await service.upload(
        actor,
        client_id,
        filename=file.filename,
        data=data,
        folder_id=folder_id,
        folder_name=folder,
        description=description,
    )


@router.patch("/{document_id}", response_model=DocumentOut, responses=ERRORS)
async def update_document(
    document_id: uuid.UUID, body: DocumentUpdate, actor: CurrentActor, service: Service
) -> DocumentOut:
    """Move to another folder or change the description."""
    return await service.update(actor, document_id, body)


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses=ERRORS,
)
async def delete_document(document_id: uuid.UUID, actor: CurrentActor, service: Service) -> None:
    await service.delete(actor, document_id)


@router.post("/clients/{client_id}/folders", response_model=ClientDocuments, responses=ERRORS)
async def create_folder(
    client_id: uuid.UUID, body: FolderIn, actor: CurrentActor, service: Service
) -> ClientDocuments:
    return await service.create_folder(actor, client_id, body)


@router.patch("/folders/{folder_id}", response_model=ClientDocuments, responses=ERRORS)
async def rename_folder(
    folder_id: uuid.UUID, body: FolderIn, actor: CurrentActor, service: Service
) -> ClientDocuments:
    return await service.rename_folder(actor, folder_id, body)


@router.delete("/folders/{folder_id}", response_model=ClientDocuments, responses=ERRORS)
async def delete_folder(
    folder_id: uuid.UUID, actor: CurrentActor, service: Service
) -> ClientDocuments:
    return await service.delete_folder(actor, folder_id)


@files_router.get(
    "/{file_id}",
    response_class=StreamingResponse,
    responses={**ERRORS, 200: {"content": {"application/octet-stream": {}}}},
)
async def download_file(
    file_id: uuid.UUID, actor: CurrentActor, service: Service
) -> StreamingResponse:
    document, stream = await service.download(actor, file_id)
    return StreamingResponse(
        stream,
        media_type=document.content_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(document.filename)}",
            "Content-Length": str(document.size),
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "sandbox",
            "Cache-Control": "private, no-store",
        },
    )
