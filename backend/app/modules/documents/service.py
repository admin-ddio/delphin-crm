"""Client documents: folders, private uploads, access-checked downloads.

Rules (product mockups; TODO(pilot-port): confirm against the pilot)
- anyone who can see the client can list and download its documents;
- upload: the client's Account Manager, its team, project managers, Super Admin;
- delete a document: its uploader, the client's Account Manager, Super Admin;
- folders: the default five (Contracts, SEO Files, Brand Assets, Reports, Other)
  can't be renamed or deleted; custom folders can, when empty (AM / Super Admin);
- PDF, Office, text/CSV, images and ZIP only, up to MAX_UPLOAD_BYTES (10 MB);
  the type comes from the extension, never from the browser's claim;
- files are stored under opaque keys and always served as attachments;
- uploads and deletions are audited and appear on the client's timeline.
"""

from __future__ import annotations

import re
import unicodedata
import uuid
from collections.abc import AsyncIterator
from pathlib import PurePath
from typing import Final

from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.actor import Actor
from app.authz.permissions import PROJECTS_CREATE
from app.core.config import Settings
from app.core.errors import BusinessRuleViolation, Conflict, Forbidden, NotFound, ValidationFailed
from app.modules.clients.models import Client
from app.modules.documents.models import Document, DocumentFolder
from app.modules.documents.repository import DocumentRepository
from app.modules.documents.schemas import (
    ClientDocuments,
    DocumentOut,
    DocumentPermissions,
    DocumentUpdate,
    FolderIn,
    FolderOut,
    UserRef,
)
from app.platform.activity.service import ActivityRecorder
from app.platform.audit.service import AuditWriter
from app.platform.identity.models import User
from app.platform.storage.interfaces import StorageBackend

#: Extension → the content type we store and serve (the browser's claim is ignored).
ALLOWED_TYPES: Final[dict[str, str]] = {
    "pdf": "application/pdf",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xls": "application/vnd.ms-excel",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "ppt": "application/vnd.ms-powerpoint",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "csv": "text/csv",
    "txt": "text/plain",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
    "svg": "image/svg+xml",
    "zip": "application/zip",
}
NOT_FOUND = "This document doesn't exist or you don't have access to it."
CLIENT_NOT_FOUND = "This client doesn't exist or you don't have access to it."
_UNSAFE = re.compile(r"[\x00-\x1f\x7f/\\:*?\"<>|]+")


def clean_filename(raw: str | None) -> str:
    name = unicodedata.normalize("NFC", PurePath((raw or "").replace("\\", "/")).name)
    name = _UNSAFE.sub("_", name).strip(" .")
    if not name:
        name = "file"
    if len(name) > 200:
        stem, dot, ext = name.rpartition(".")
        name = (stem[: 200 - len(ext) - 1] + dot + ext) if dot else name[:200]
    return name


def extension(name: str) -> str:
    return name.rpartition(".")[2].lower() if "." in name else ""


def _ref(user: User | None) -> UserRef | None:
    return UserRef(id=user.id, full_name=user.full_name) if user else None


class DocumentService:
    def __init__(
        self, session: AsyncSession, *, storage: StorageBackend, settings: Settings
    ) -> None:
        self._repo = DocumentRepository(session)
        self._storage = storage
        self._settings = settings
        self._audit = AuditWriter(session)
        self._activity = ActivityRecorder(session)

    # ------------------------------------------------------------ reads

    async def for_client(self, actor: Actor, client_id: uuid.UUID) -> ClientDocuments:
        client = await self._client(actor, client_id)
        folders = await self._repo.folders(client.id)
        counts = await self._repo.folder_counts([f.id for f in folders])
        return ClientDocuments(
            folders=[
                FolderOut(id=f.id, name=f.name, is_system=f.is_system, count=counts.get(f.id, 0))
                for f in folders
            ],
            documents=[
                self._out(actor, client, doc, user)
                for doc, user in await self._repo.documents(client.id)
            ],
            permissions=DocumentPermissions(
                upload=await self._can_upload(actor, client),
                manage_folders=self._is_manager(actor, client),
            ),
            max_upload_bytes=self._settings.max_upload_bytes,
            allowed_extensions=sorted(ALLOWED_TYPES),
        )

    async def download(
        self, actor: Actor, document_id: uuid.UUID
    ) -> tuple[Document, AsyncIterator[bytes]]:
        found = await self._repo.document(document_id)
        if found is None or await self._repo.visible_client(actor, found[0].client_id) is None:
            raise NotFound(NOT_FOUND)
        document = found[0]
        return document, self._storage.open(document.storage_key)

    # ------------------------------------------------------------ writes

    async def upload(
        self,
        actor: Actor,
        client_id: uuid.UUID,
        *,
        filename: str | None,
        data: bytes,
        folder_id: uuid.UUID | None = None,
        folder_name: str | None = None,
        description: str | None = None,
    ) -> DocumentOut:
        client = await self._client(actor, client_id)
        if not await self._can_upload(actor, client):
            raise Forbidden("Only the client's Account Manager and team can upload documents.")
        name = clean_filename(filename)
        ext = extension(name)
        if ext not in ALLOWED_TYPES:
            raise ValidationFailed(
                "This file type isn't allowed. Upload PDF, Office, text, image or ZIP files.",
                details={"allowed": sorted(ALLOWED_TYPES)},
            )
        if not data:
            raise ValidationFailed("The file is empty.")
        if len(data) > self._settings.max_upload_bytes:
            limit = self._settings.max_upload_bytes // (1024 * 1024)
            raise ValidationFailed(f"The file is larger than {limit} MB.")
        folder = await self._folder(client, folder_id, folder_name)

        key = f"clients/{client.id.hex}/{uuid.uuid4().hex}"
        stored = await self._storage.put(key, data, content_type=ALLOWED_TYPES[ext])
        document = Document(
            client_id=client.id,
            folder_id=folder.id,
            filename=name,
            content_type=stored.content_type,
            size=stored.size,
            sha256=stored.sha256,
            storage_key=stored.key,
            description=(description or "").strip()[:500] or None,
            uploaded_by_id=actor.user_id,
        )
        self._repo.add(document)
        await self._repo.flush()
        await self._log(
            actor,
            client,
            "document.uploaded",
            f"Document uploaded: {name} ({folder.name})",
            document,
        )
        uploader = await self._uploader(document)
        return self._out(actor, client, document, uploader)

    async def update(
        self, actor: Actor, document_id: uuid.UUID, data: DocumentUpdate
    ) -> DocumentOut:
        document, uploader, client = await self._document(actor, document_id)
        if not self._can_delete(actor, client, document):
            raise Forbidden("Only the uploader or the client's Account Manager can change this.")
        incoming = data.model_dump(exclude_unset=True)
        if incoming.get("folder_id"):
            folder = await self._repo.folder(incoming["folder_id"])
            if folder is None or folder.client_id != client.id:
                raise ValidationFailed("Choose one of this client's folders.")
            document.folder_id = folder.id
        if "description" in incoming:
            document.description = incoming["description"]
        await self._repo.flush()
        return self._out(actor, client, document, uploader)

    async def delete(self, actor: Actor, document_id: uuid.UUID) -> None:
        document, _, client = await self._document(actor, document_id)
        if not self._can_delete(actor, client, document):
            raise Forbidden("Only the uploader or the client's Account Manager can delete this.")
        key, name = document.storage_key, document.filename
        await self._repo.delete(document)
        await self._log(actor, client, "document.deleted", f"Document deleted: {name}", document)
        await self._storage.delete(key)

    async def create_folder(
        self, actor: Actor, client_id: uuid.UUID, data: FolderIn
    ) -> ClientDocuments:
        client = await self._client(actor, client_id)
        self._require_manager(actor, client)
        await self._repo.folders(client.id)
        if await self._repo.folder_named(client.id, data.name):
            raise Conflict(f"There is already a folder called {data.name}.")
        self._repo.add(
            DocumentFolder(client_id=client.id, name=data.name, created_by_id=actor.user_id)
        )
        await self._repo.flush()
        return await self.for_client(actor, client.id)

    async def rename_folder(
        self, actor: Actor, folder_id: uuid.UUID, data: FolderIn
    ) -> ClientDocuments:
        folder, client = await self._custom_folder(actor, folder_id)
        same = await self._repo.folder_named(client.id, data.name)
        if same is not None and same.id != folder.id:
            raise Conflict(f"There is already a folder called {data.name}.")
        folder.name = data.name
        await self._repo.flush()
        return await self.for_client(actor, client.id)

    async def delete_folder(self, actor: Actor, folder_id: uuid.UUID) -> ClientDocuments:
        folder, client = await self._custom_folder(actor, folder_id)
        if (await self._repo.folder_counts([folder.id])).get(folder.id):
            raise BusinessRuleViolation("Move or delete the folder's documents first.")
        await self._repo.delete(folder)
        return await self.for_client(actor, client.id)

    # ------------------------------------------------------------ helpers

    async def _client(self, actor: Actor, client_id: uuid.UUID) -> Client:
        client = await self._repo.visible_client(actor, client_id)
        if client is None:
            raise NotFound(CLIENT_NOT_FOUND)
        return client

    async def _document(
        self, actor: Actor, document_id: uuid.UUID
    ) -> tuple[Document, User | None, Client]:
        found = await self._repo.document(document_id)
        client = await self._repo.visible_client(actor, found[0].client_id) if found else None
        if found is None or client is None:
            raise NotFound(NOT_FOUND)
        return found[0], found[1], client

    async def _folder(
        self, client: Client, folder_id: uuid.UUID | None, folder_name: str | None
    ) -> DocumentFolder:
        folders = await self._repo.folders(client.id)
        if folder_id is not None:
            folder = next((f for f in folders if f.id == folder_id), None)
        else:
            wanted = (folder_name or "Other").lower()
            folder = next((f for f in folders if f.name.lower() == wanted), None)
        if folder is None:
            raise ValidationFailed("Choose one of this client's folders.")
        return folder

    async def _custom_folder(
        self, actor: Actor, folder_id: uuid.UUID
    ) -> tuple[DocumentFolder, Client]:
        folder = await self._repo.folder(folder_id)
        client = await self._repo.visible_client(actor, folder.client_id) if folder else None
        if folder is None or client is None:
            raise NotFound("This folder doesn't exist or you don't have access to it.")
        self._require_manager(actor, client)
        if folder.is_system:
            raise BusinessRuleViolation("Default folders can't be renamed or deleted.")
        return folder, client

    @staticmethod
    def _is_manager(actor: Actor, client: Client) -> bool:
        return actor.is_super_admin or client.account_manager_id == actor.user_id

    def _require_manager(self, actor: Actor, client: Client) -> None:
        if not self._is_manager(actor, client):
            raise Forbidden("Only the client's Account Manager can manage folders.")

    async def _can_upload(self, actor: Actor, client: Client) -> bool:
        return (
            self._is_manager(actor, client)
            or actor.can(PROJECTS_CREATE)
            or await self._repo.on_team(client.id, actor.user_id)
        )

    def _can_delete(self, actor: Actor, client: Client, document: Document) -> bool:
        return self._is_manager(actor, client) or document.uploaded_by_id == actor.user_id

    async def _uploader(self, document: Document) -> User | None:
        found = await self._repo.document(document.id)
        return found[1] if found else None

    def _out(
        self, actor: Actor, client: Client, document: Document, uploader: User | None
    ) -> DocumentOut:
        return DocumentOut(
            id=document.id,
            folder_id=document.folder_id,
            filename=document.filename,
            content_type=document.content_type,
            size=document.size,
            description=document.description,
            uploaded_by=_ref(uploader),
            uploaded_at=document.uploaded_at,
            download_url=f"/api/v1/files/{document.id}",
            can_delete=self._can_delete(actor, client, document),
        )

    async def _log(
        self, actor: Actor, client: Client, action: str, summary: str, document: Document
    ) -> None:
        await self._audit.record(
            action=action,
            entity_type="document",
            entity_id=document.id,
            actor_user_id=actor.user_id,
            changes={"filename": document.filename, "size": document.size},
            context={"client_id": str(client.id)},
        )
        await self._activity.record(
            verb=action.removeprefix("document."),
            subject_type="client",
            subject_id=client.id,
            actor_user_id=actor.user_id,
            summary=summary,
        )
