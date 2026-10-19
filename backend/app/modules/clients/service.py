"""Clients: create, list, view, edit, with the demo's duplicate rules.

Rules (clickable demo; TODO(pilot-port): confirm against services/clients.ts):
- duplicate DOMAIN is a hard block (never overridable);
- a similar NAME (normalised: case, punctuation, "&", legal suffixes) is a
  warning, overridable with "This is a different business";
- codes are CL-0001, CL-0002… from the transactional counter;
- the Account Manager must be an active Account Manager or Super Admin;
- only the client's own Account Manager (or Super Admin) may edit it;
- clients outside the actor's scope are reported as not found, never forbidden;
- every create/update is audited (with field changes) and logged as activity.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.actor import Actor
from app.authz.permissions import CLIENTS_UPDATE
from app.core.errors import Conflict, Forbidden, NotFound, ValidationFailed
from app.core.pagination import Page, PageParams, parse_sort
from app.modules.clients.models import Client
from app.modules.clients.repository import SORTS, ClientRepository
from app.modules.clients.rules import STATUS_LABELS, domain_of, normalize_name
from app.modules.clients.schemas import (
    AccountManagerOption,
    ClientActivity,
    ClientCreate,
    ClientDetail,
    ClientListItem,
    ClientUpdate,
    UserRef,
)
from app.platform.activity.service import ActivityRecorder
from app.platform.audit.service import AuditWriter
from app.platform.identity.models import User
from app.platform.system.counters import format_code, next_value

EDITABLE_FIELDS = (
    "name",
    "website",
    "industry",
    "contact_name",
    "contact_email",
    "account_manager_id",
)


def _ref(user: User) -> UserRef:
    return UserRef(id=user.id, full_name=user.full_name)


class ClientService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = ClientRepository(session)
        self._audit = AuditWriter(session)
        self._activity = ActivityRecorder(session)

    # ------------------------------------------------------------ reads

    async def list_clients(
        self,
        actor: Actor,
        params: PageParams,
        *,
        search: str | None = None,
        status: str | None = None,
        sort: str | None = None,
    ) -> Page[ClientListItem]:
        rows, total = await self._repo.page(
            actor, params, search=search, status=status, sort=parse_sort(sort, SORTS)
        )
        items = [
            ClientListItem(
                id=client.id,
                code=client.code,
                name=client.name,
                domain=client.domain,
                status=client.status,  # type: ignore[arg-type]  # DB check constraint
                status_label=STATUS_LABELS[client.status],
                account_manager=_ref(manager),
                created_at=client.created_at,
            )
            for client, manager in rows
        ]
        return Page[ClientListItem].create(items, total, params)

    async def get(self, actor: Actor, client_id: uuid.UUID) -> ClientDetail:
        client, manager = await self._visible(actor, client_id)
        return self._detail(actor, client, manager)

    async def activity(self, actor: Actor, client_id: uuid.UUID) -> list[ClientActivity]:
        await self._visible(actor, client_id)
        return [
            ClientActivity(
                id=event.id,
                occurred_at=event.occurred_at,
                summary=event.summary or event.verb,
                actor=_ref(user) if user else None,
            )
            for event, user in await self._repo.activity(client_id)
        ]

    async def account_manager_options(self) -> list[AccountManagerOption]:
        return [
            AccountManagerOption(id=user.id, full_name=user.full_name, email=user.email)
            for user in await self._repo.account_manager_options()
        ]

    # ------------------------------------------------------------ writes

    async def create(self, actor: Actor, data: ClientCreate) -> ClientDetail:
        manager = await self._account_manager(data.account_manager_id)
        domain = domain_of(data.website)
        normalized = normalize_name(data.name)
        await self._check_duplicates(
            domain, normalized, confirm_different=data.confirm_different_business
        )

        number = await next_value(self._session, "client")
        client = Client(
            code=format_code("CL", number),
            name=data.name,
            normalized_name=normalized,
            website=data.website,
            domain=domain,
            industry=data.industry,
            contact_name=data.contact_name,
            contact_email=str(data.contact_email) if data.contact_email else None,
            account_manager_id=manager.id,
            created_by_id=actor.user_id,
        )
        try:
            await self._repo.add(client)
        except IntegrityError as exc:  # lost a race on the unique domain
            raise Conflict(
                f"A client with the domain {domain} already exists.",
                details={"reason": "duplicate_domain"},
            ) from exc

        await self._audit.record(
            action="client.created",
            entity_type="client",
            entity_id=client.id,
            actor_user_id=actor.user_id,
            changes={field: self._value(client, field) for field in EDITABLE_FIELDS},
            context={"code": client.code},
        )
        await self._activity.record(
            verb="created",
            subject_type="client",
            subject_id=client.id,
            actor_user_id=actor.user_id,
            summary=f"Client {client.name} created",
        )
        return self._detail(actor, client, manager)

    async def update(self, actor: Actor, client_id: uuid.UUID, data: ClientUpdate) -> ClientDetail:
        client, manager = await self._visible(actor, client_id)
        if not self._can_edit(actor, client):
            raise Forbidden("Only the client's Account Manager can edit it.")

        incoming = data.model_dump(exclude_unset=True, exclude={"confirm_different_business"})
        if incoming.get("name") is None and "name" in incoming:
            raise ValidationFailed("The client name can't be empty.")
        if "account_manager_id" in incoming:
            if incoming["account_manager_id"] is None:
                raise ValidationFailed("A client must have an Account Manager.")
            manager = await self._account_manager(incoming["account_manager_id"])
        if "contact_email" in incoming and incoming["contact_email"] is not None:
            incoming["contact_email"] = str(incoming["contact_email"])

        changes: dict[str, Any] = {}
        for field, new in incoming.items():
            old = getattr(client, field)
            if old != new:
                changes[field] = [self._jsonable(old), self._jsonable(new)]
        if not changes:
            return self._detail(actor, client, manager)

        if "name" in changes or "website" in changes:
            domain = domain_of(incoming.get("website", client.website))
            normalized = normalize_name(incoming.get("name", client.name))
            await self._check_duplicates(
                domain if "website" in changes else None,
                normalized if "name" in changes else "",
                confirm_different=data.confirm_different_business,
                exclude=client.id,
            )
            client.domain = domain
            client.normalized_name = normalized

        for field in changes:
            setattr(client, field, incoming[field])
        try:
            await self._repo.flush()
        except IntegrityError as exc:
            raise Conflict(
                "A client with that domain already exists.",
                details={"reason": "duplicate_domain"},
            ) from exc

        await self._audit.record(
            action="client.updated",
            entity_type="client",
            entity_id=client.id,
            actor_user_id=actor.user_id,
            changes=changes,
        )
        await self._activity.record(
            verb="updated",
            subject_type="client",
            subject_id=client.id,
            actor_user_id=actor.user_id,
            summary="Client details updated: "
            + ", ".join(field.replace("_id", "").replace("_", " ") for field in changes),
        )
        return self._detail(actor, client, manager)

    # ------------------------------------------------------------ helpers

    async def _visible(self, actor: Actor, client_id: uuid.UUID) -> tuple[Client, User]:
        found = await self._repo.get(actor, client_id)
        if found is None:
            # Out-of-scope clients are indistinguishable from missing ones (demo rule).
            raise NotFound("This client doesn't exist or you don't have access to it.")
        return found

    async def _account_manager(self, user_id: uuid.UUID) -> User:
        manager = await self._repo.eligible_account_manager(user_id)
        if manager is None:
            raise ValidationFailed(
                "Choose an active Account Manager.", details={"account_manager_id": str(user_id)}
            )
        return manager

    async def _check_duplicates(
        self,
        domain: str | None,
        normalized: str,
        *,
        confirm_different: bool,
        exclude: uuid.UUID | None = None,
    ) -> None:
        if domain:
            existing = await self._repo.by_domain(domain, exclude=exclude)
            if existing is not None:
                raise Conflict(
                    f"A client with the domain {domain} already exists ({existing.name}).",
                    details={
                        "reason": "duplicate_domain",
                        "client": {
                            "id": str(existing.id),
                            "code": existing.code,
                            "name": existing.name,
                        },
                    },
                )
        if normalized and not confirm_different:
            similar = await self._repo.by_normalized_name(normalized, exclude=exclude)
            if similar is not None:
                raise Conflict(
                    f"A client with a similar name already exists: {similar.name}. "
                    'Tick "This is a different business" to continue.',
                    details={
                        "reason": "similar_name",
                        "client": {
                            "id": str(similar.id),
                            "code": similar.code,
                            "name": similar.name,
                        },
                    },
                )

    @staticmethod
    def _can_edit(actor: Actor, client: Client) -> bool:
        return actor.is_super_admin or (
            actor.can(CLIENTS_UPDATE) and client.account_manager_id == actor.user_id
        )

    def _detail(self, actor: Actor, client: Client, manager: User) -> ClientDetail:
        return ClientDetail(
            id=client.id,
            code=client.code,
            name=client.name,
            website=client.website,
            domain=client.domain,
            industry=client.industry,
            contact_name=client.contact_name,
            contact_email=client.contact_email,
            status=client.status,  # type: ignore[arg-type]  # DB check constraint
            status_label=STATUS_LABELS[client.status],
            account_manager=_ref(manager),
            created_at=client.created_at,
            updated_at=client.updated_at,
            can_edit=self._can_edit(actor, client),
        )

    @staticmethod
    def _jsonable(value: object) -> object:
        return str(value) if isinstance(value, uuid.UUID) else value

    @classmethod
    def _value(cls, client: Client, field: str) -> object:
        return cls._jsonable(getattr(client, field))
