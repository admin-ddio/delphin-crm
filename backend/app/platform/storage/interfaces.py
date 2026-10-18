"""Storage interface. Files are never served from a public path: the documents
module streams them through GET /api/v1/files/{id} after re-checking access."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class StoredObject:
    key: str
    size: int
    sha256: str
    content_type: str


class StorageBackend(Protocol):
    async def put(self, key: str, data: bytes, *, content_type: str) -> StoredObject: ...

    def open(self, key: str) -> AsyncIterator[bytes]:
        """Stream the object's bytes."""
        ...

    async def delete(self, key: str) -> None: ...

    async def exists(self, key: str) -> bool: ...
