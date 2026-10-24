"""HTTP surface of the clients module."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.actor import Actor
from app.authz.dependencies import CurrentActor, require_any, require_permission
from app.authz.permissions import CLIENTS_CREATE, CLIENTS_UPDATE
from app.core.errors import AUTH_ERROR_RESPONSES, ErrorEnvelope
from app.core.pagination import Page, PageParams, page_params
from app.db.session import get_session
from app.modules.clients.schemas import (
    AccountManagerOption,
    ClientActivity,
    ClientCreate,
    ClientDetail,
    ClientListItem,
    ClientStatus,
    ClientUpdate,
    StatusChange,
    StatusCounts,
)
from app.modules.clients.service import ClientService

TAG = {"name": "clients", "description": "CRM & Clients"}

router = APIRouter(prefix="/clients", tags=["clients"])

NOT_FOUND: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorEnvelope, "description": "Not found, or outside your access"}
}
RULES: dict[int | str, dict[str, Any]] = {
    422: {"model": ErrorEnvelope, "description": "Business rule violated"}
}
DUPLICATE: dict[int | str, dict[str, Any]] = {
    409: {
        "model": ErrorEnvelope,
        "description": "Duplicate domain, or similar name (details.reason)",
    }
}


def get_client_service(session: Annotated[AsyncSession, Depends(get_session)]) -> ClientService:
    return ClientService(session)


Service = Annotated[ClientService, Depends(get_client_service)]


@router.get("", response_model=Page[ClientListItem], responses=AUTH_ERROR_RESPONSES)
async def list_clients(
    *,
    actor: CurrentActor,
    service: Service,
    params: Annotated[PageParams, Depends(page_params)],
    q: Annotated[str | None, Query(max_length=200, description="Name, code or domain")] = None,
    status_filter: Annotated[ClientStatus | None, Query(alias="status")] = None,
    sort: Annotated[str | None, Query(description="name | code | created_at, '-' = desc")] = None,
) -> Page[ClientListItem]:
    """Clients the actor may see, alphabetical by default."""
    return await service.list_clients(actor, params, search=q, status=status_filter, sort=sort)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ClientDetail,
    responses={**AUTH_ERROR_RESPONSES, **DUPLICATE},
)
async def create_client(
    body: ClientCreate,
    actor: Annotated[Actor, Depends(require_permission(CLIENTS_CREATE))],
    service: Service,
) -> ClientDetail:
    return await service.create(actor, body)


@router.get("/counts", response_model=StatusCounts, responses=AUTH_ERROR_RESPONSES)
async def status_counts(actor: CurrentActor, service: Service) -> StatusCounts:
    """Visible clients per status (list tabs)."""
    return await service.status_counts(actor)


@router.get(
    "/account-managers",
    response_model=list[AccountManagerOption],
    responses=AUTH_ERROR_RESPONSES,
)
async def account_manager_options(
    actor: Annotated[Actor, Depends(require_any(CLIENTS_CREATE, CLIENTS_UPDATE))],
    service: Service,
) -> list[AccountManagerOption]:
    """People who can be a client's Account Manager."""
    return await service.account_manager_options()


@router.get(
    "/{client_id}",
    response_model=ClientDetail,
    responses={**AUTH_ERROR_RESPONSES, **NOT_FOUND},
)
async def get_client(client_id: uuid.UUID, actor: CurrentActor, service: Service) -> ClientDetail:
    return await service.get(actor, client_id)


@router.patch(
    "/{client_id}",
    response_model=ClientDetail,
    responses={**AUTH_ERROR_RESPONSES, **NOT_FOUND, **DUPLICATE},
)
async def update_client(
    client_id: uuid.UUID,
    body: ClientUpdate,
    actor: CurrentActor,
    service: Service,
) -> ClientDetail:
    """Partial update; only the client's Account Manager (or Super Admin) may edit."""
    return await service.update(actor, client_id, body)


@router.get(
    "/{client_id}/activity",
    response_model=list[ClientActivity],
    responses={**AUTH_ERROR_RESPONSES, **NOT_FOUND},
)
async def client_activity(
    client_id: uuid.UUID, actor: CurrentActor, service: Service
) -> list[ClientActivity]:
    """Newest first (last 100)."""
    return await service.activity(actor, client_id)


@router.post(
    "/{client_id}/status",
    response_model=ClientDetail,
    responses={**AUTH_ERROR_RESPONSES, **NOT_FOUND, **RULES},
)
async def change_status(
    client_id: uuid.UUID, body: StatusChange, actor: CurrentActor, service: Service
) -> ClientDetail:
    """Put on hold, mark completed, or reactivate (the client's Account Manager)."""
    return await service.change_status(actor, client_id, body.action)
