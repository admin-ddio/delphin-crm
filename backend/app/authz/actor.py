"""The authenticated principal a request acts as."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.authz.permissions import WILDCARD


@dataclass(frozen=True, slots=True)
class Actor:
    user_id: UUID
    email: str
    full_name: str
    roles: frozenset[str]
    permissions: frozenset[str]

    @property
    def is_super_admin(self) -> bool:
        return WILDCARD in self.permissions

    def can(self, permission: str) -> bool:
        return self.is_super_admin or permission in self.permissions

    def can_any(self, *permissions: str) -> bool:
        return any(self.can(permission) for permission in permissions)

    def can_all(self, *permissions: str) -> bool:
        return all(self.can(permission) for permission in permissions)
