"""Request/response models for the documents module."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field


def _strip(value: object) -> object:
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


class UserRef(BaseModel):
    id: uuid.UUID
    full_name: str


class FolderOut(BaseModel):
    id: uuid.UUID
    name: str
    is_system: bool
    count: int


class DocumentOut(BaseModel):
    id: uuid.UUID
    folder_id: uuid.UUID
    filename: str
    content_type: str
    size: int
    description: str | None
    uploaded_by: UserRef | None
    uploaded_at: datetime
    #: GET this (signed in) to download; files are never public.
    download_url: str
    can_delete: bool


class DocumentPermissions(BaseModel):
    upload: bool
    manage_folders: bool


class ClientDocuments(BaseModel):
    folders: list[FolderOut]
    documents: list[DocumentOut]
    permissions: DocumentPermissions
    max_upload_bytes: int
    allowed_extensions: list[str]


class FolderIn(BaseModel):
    name: Annotated[str, BeforeValidator(_strip)] = Field(min_length=1, max_length=60)


class DocumentUpdate(BaseModel):
    folder_id: uuid.UUID | None = None
    description: Annotated[str | None, BeforeValidator(_strip)] = Field(
        default=None, max_length=500
    )
