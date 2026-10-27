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
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.actor import Actor
from app.authz.permissions import CLIENTS_UPDATE
from app.core.clock import SystemClock
from app.core.errors import BusinessRuleViolation, Conflict, Forbidden, NotFound, ValidationFailed
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
    StatusCounts,
    UserRef,
)
from app.modules.notifications.service import NotificationService
from app.modules.services.service import ServicesService
from app.platform.activity.service import ActivityRecorder
from app.platform.audit.service import AuditWriter
from app.platform.identity.models import User
from app.platform.notifications.interfaces import NotificationRequest
from app.platform.system.counters import format_code, next_value

EDITABLE_FIELDS = (
    "name",
    "website",
    "industry",
    "business_type",
    "company_size",
    "country",
    "description",
    "contact_name",
    "contact_designation",
    "contact_email",
    "contact_phone",
    "contact_alt_email",
    "contact_alt_phone",
    "contract_start",
    "contract_end",
    "contract_value",
    "payment_terms",
    "contract_notes",
    "account_manager_id",
)
#: Required on the create form; an edit may change but not clear them.
REQUIRED_FIELDS = {
    "name": "The company name",
    "industry": "The industry",
    "country": "The country",
    "contact_name": "The contact name",
    "contact_designation": "The contact's designation",
    "contact_email": "The contact e-mail",
    "contact_phone": "The contact phone",
    "contract_start": "The contract start date",
    "contract_end": "The contract end date",
}
EMAIL_FIELDS = ("contact_email", "contact_alt_email")
DETAIL_FIELDS = (
    "id",
    "code",
    "name",
    "website",
    "domain",
    "industry",
    "business_type",
    "company_size",
    "country",
    "description",
    "contact_name",
    "contact_designation",
    "contact_email",
    "contact_phone",
    "contact_alt_email",
    "contact_alt_phone",
    "contract_start",
    "contract_end",
    "contract_value",
    "contract_currency",
    "payment_terms",
    "contract_notes",
)


def _ref(user: User) -> UserRef:
    return UserRef(id=user.id, full_name=user.full_name)


class ClientService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = ClientRepository(session)
        self._audit = AuditWriter(session)
        self._activity = ActivityRecorder(session)
        self._notifier = NotificationService(session)

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
        last = await self._repo.last_activity([client.id for client, _ in rows])
        items = [
            ClientListItem(
                id=client.id,
                code=client.code,
                name=client.name,
                website=client.website,
                domain=client.domain,
                industry=client.industry,
                status=client.status,  # type: ignore[arg-type]  # DB check constraint
                status_label=STATUS_LABELS[client.status],
                account_manager=_ref(manager),
                created_at=client.created_at,
                last_activity_at=last.get(client.id),
            )
            for client, manager in rows
        ]
        return Page[ClientListItem].create(items, total, params)

    async def status_counts(self, actor: Actor) -> StatusCounts:
        counts = await self._repo.status_counts(actor)
        return StatusCounts(
            all=sum(counts.values()),
            onboarding=counts.get("onboarding", 0),
            active=counts.get("active", 0),
            on_hold=counts.get("on_hold", 0),
            completed=counts.get("completed", 0),
        )

    async def get(self, actor: Actor, client_id: uuid.UUID) -> ClientDetail:
        client, manager = await self._visible(actor, client_id)
        return await self._detail(actor, client, manager)

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
        fields = data.model_dump(
            include=set(EDITABLE_FIELDS) - {"account_manager_id"}, exclude_none=True
        )
        for name in EMAIL_FIELDS:
            if name in fields:
                fields[name] = str(fields[name])
        client = Client(
            code=format_code("CL", number),
            normalized_name=normalized,
            domain=domain,
            status="onboarding",  # the contract is signed before the client is created
            account_manager_id=manager.id,
            created_by_id=actor.user_id,
            **fields,
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
        await ServicesService(self._session, clock=SystemClock()).add_for_client(
            actor, client, data.services, at_creation=True
        )
        if manager.id != actor.user_id:
            await self._notifier.notify(
                NotificationRequest(
                    user_id=manager.id,
                    kind="client.assigned",
                    title=f"You're the Account Manager for {client.name}",
                    body="Onboarding has started. Complete the profile and send the questionnaire.",
                    link=f"/clients/{client.id}",
                    entity_type="client",
                    entity_id=str(client.id),
                )
            )
        return await self._detail(actor, client, manager)

    async def update(  # noqa: PLR0912  # one guard per editable field group
        self, actor: Actor, client_id: uuid.UUID, data: ClientUpdate
    ) -> ClientDetail:
        client, manager = await self._visible(actor, client_id)
        if not self._can_edit(actor, client):
            raise Forbidden("Only the client's Account Manager can edit it.")

        incoming = data.model_dump(exclude_unset=True, exclude={"confirm_different_business"})
        for name, label in REQUIRED_FIELDS.items():
            if name in incoming and incoming[name] is None:
                raise ValidationFailed(f"{label} can't be empty.")
        if "account_manager_id" in incoming:
            if incoming["account_manager_id"] is None:
                raise ValidationFailed("A client must have an Account Manager.")
            manager = await self._account_manager(incoming["account_manager_id"])
        for name in EMAIL_FIELDS:
            if incoming.get(name) is not None:
                incoming[name] = str(incoming[name])
        start = incoming.get("contract_start", client.contract_start)
        end = incoming.get("contract_end", client.contract_end)
        if start and end and end < start:
            raise ValidationFailed("The contract end date must be on or after the start date.")

        changes: dict[str, Any] = {}
        for field, new in incoming.items():
            old = getattr(client, field)
            if old != new:
                changes[field] = [self._jsonable(old), self._jsonable(new)]
        if not changes:
            return await self._detail(actor, client, manager)

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
        return await self._detail(actor, client, manager)

    async def change_status(self, actor: Actor, client_id: uuid.UUID, action: str) -> ClientDetail:
        """On hold / Completed / reactivate (the AM's manual lifecycle states)."""
        client, manager = await self._visible(actor, client_id)
        if not self._can_edit(actor, client):
            raise Forbidden("Only the client's Account Manager can change its status.")
        previous = client.status
        if action == "hold":
            if previous not in ("onboarding", "active"):
                raise BusinessRuleViolation("Only onboarding or active clients can be put on hold.")
            client.status = "on_hold"
        elif action == "complete":
            if previous not in ("active", "on_hold") or not await self._repo.onboarded(client.id):
                raise BusinessRuleViolation(
                    "Only clients whose onboarding is completed can be marked completed."
                )
            client.status = "completed"
        else:
            if previous not in ("on_hold", "completed"):
                raise BusinessRuleViolation("Only clients on hold or completed can be reactivated.")
            client.status = "active" if await self._repo.onboarded(client.id) else "onboarding"
        await self._repo.flush()
        label = STATUS_LABELS[client.status]
        await self._audit.record(
            action="client.status_changed",
            entity_type="client",
            entity_id=client.id,
            actor_user_id=actor.user_id,
            changes={"status": [previous, client.status]},
        )
        await self._activity.record(
            verb="status_changed",
            subject_type="client",
            subject_id=client.id,
            actor_user_id=actor.user_id,
            summary=f"Client status: {STATUS_LABELS[previous]} → {label}",
        )
        return await self._detail(actor, client, manager)

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

    async def _detail(self, actor: Actor, client: Client, manager: User) -> ClientDetail:
        last = await self._repo.last_activity([client.id])
        fields = {name: getattr(client, name) for name in DETAIL_FIELDS}
        if client.contract_value is not None:  # always two decimals, as stored
            fields["contract_value"] = Decimal(client.contract_value).quantize(Decimal("0.01"))
        return ClientDetail(
            **fields,
            status=client.status,  # type: ignore[arg-type]  # DB check constraint
            status_label=STATUS_LABELS[client.status],
            account_manager=_ref(manager),
            created_at=client.created_at,
            updated_at=client.updated_at,
            last_activity_at=last.get(client.id),
            can_edit=self._can_edit(actor, client),
        )

    @staticmethod
    def _jsonable(value: object) -> object:
        if isinstance(value, uuid.UUID | date | Decimal):
            return str(value)
        return value

    @classmethod
    def _value(cls, client: Client, field: str) -> object:
        return cls._jsonable(getattr(client, field))
