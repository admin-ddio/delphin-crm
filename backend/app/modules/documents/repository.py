"""Queries for client documents. Callers check client visibility first (ClientScope)."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.actor import Actor
from app.authz.scopes import apply_scope
from app.modules.clients.models import Client, ClientTeamMember
from app.modules.clients.repository import ClientScope
from app.modules.documents.models import DEFAULT_FOLDERS, Document, DocumentFolder
from app.platform.identity.models import User


class DocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def visible_client(self, actor: Actor, client_id: uuid.UUID) -> Client | None:
        stmt = apply_scope(select(Client).where(Client.id == client_id), actor, ClientScope())
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def on_team(self, client_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        stmt = select(ClientTeamMember.user_id).where(
            ClientTeamMember.client_id == client_id, ClientTeamMember.user_id == user_id
        )
        return (await self._session.execute(stmt)).first() is not None

    async def folders(self, client_id: uuid.UUID) -> list[DocumentFolder]:
        """The client's folders, creating the default set on first use."""
        stmt = (
            select(DocumentFolder)
            .where(DocumentFolder.client_id == client_id)
            .order_by(DocumentFolder.position, DocumentFolder.name)
        )
        rows = list((await self._session.execute(stmt)).scalars())
        if rows:
            return rows
        for position, name in enumerate(DEFAULT_FOLDERS):
            self._session.add(
                DocumentFolder(client_id=client_id, name=name, position=position, is_system=True)
            )
        await self._session.flush()
        return list((await self._session.execute(stmt)).scalars())

    async def folder(self, folder_id: uuid.UUID) -> DocumentFolder | None:
        return await self._session.get(DocumentFolder, folder_id)

    async def folder_named(self, client_id: uuid.UUID, name: str) -> DocumentFolder | None:
        stmt = select(DocumentFolder).where(
            DocumentFolder.client_id == client_id, DocumentFolder.name == name
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def documents(self, client_id: uuid.UUID) -> list[tuple[Document, User | None]]:
        rows = await self._session.execute(
            select(Document, User)
            .outerjoin(User, User.id == Document.uploaded_by_id)
            .where(Document.client_id == client_id)
            .order_by(Document.uploaded_at.desc(), Document.id)
        )
        return [(doc, user) for doc, user in rows.all()]

    async def document(self, document_id: uuid.UUID) -> tuple[Document, User | None] | None:
        row = (
            await self._session.execute(
                select(Document, User)
                .outerjoin(User, User.id == Document.uploaded_by_id)
                .where(Document.id == document_id)
            )
        ).one_or_none()
        if row is None:
            return None
        doc, user = row
        return doc, user

    async def folder_counts(self, folder_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, int]:
        if not folder_ids:
            return {}
        rows = await self._session.execute(
            select(Document.folder_id, func.count())
            .where(Document.folder_id.in_(folder_ids))
            .group_by(Document.folder_id)
        )
        return {folder: int(count) for folder, count in rows.all()}

    async def count_in(self, client_id: uuid.UUID, folder_name: str) -> int:
        stmt = (
            select(func.count())
            .select_from(Document)
            .join(DocumentFolder, DocumentFolder.id == Document.folder_id)
            .where(Document.client_id == client_id, DocumentFolder.name == folder_name)
        )
        return int((await self._session.execute(stmt)).scalar_one())

    def add(self, obj: Document | DocumentFolder) -> None:
        self._session.add(obj)

    async def delete(self, obj: Document | DocumentFolder) -> None:
        await self._session.delete(obj)
        await self._session.flush()

    async def flush(self) -> None:
        await self._session.flush()
