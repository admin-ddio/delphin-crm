"""HTTP surface of the services module: catalogue, templates, client services, retainers."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.dependencies import CurrentActor
from app.core.clock import Clock, get_clock
from app.core.errors import AUTH_ERROR_RESPONSES, ErrorEnvelope
from app.db.session import get_session
from app.modules.services.schemas import (
    AddServices,
    GenerateResult,
    ServiceDetail,
    ServiceItem,
    ServiceKind,
    ServicesOverview,
    ServiceStatus,
    ServiceTemplates,
    ServiceTypeOut,
    StartOptions,
    StartService,
    TemplateUpdate,
)
from app.modules.services.service import ServicesService

TAG = {"name": "services", "description": "Services, retainers, templates and workspaces"}

router = APIRouter(prefix="/services", tags=["services"])

ERRORS: dict[int | str, dict[str, Any]] = {
    **AUTH_ERROR_RESPONSES,
    404: {"model": ErrorEnvelope, "description": "Not found (or not visible)"},
    409: {"model": ErrorEnvelope, "description": "The client already has that retainer"},
    422: {"model": ErrorEnvelope, "description": "Validation failed or business rule violated"},
}


def get_services_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> ServicesService:
    return ServicesService(session, clock=clock)


Service = Annotated[ServicesService, Depends(get_services_service)]


@router.get("/types", response_model=list[ServiceTypeOut], responses=AUTH_ERROR_RESPONSES)
async def list_service_types(actor: CurrentActor, service: Service) -> list[ServiceTypeOut]:
    """What Delphin sells: SEO and Social Media retainers; Website, Web App, Mobile App."""
    return await service.types()


@router.get("/types/{key}/templates", response_model=ServiceTemplates, responses=ERRORS)
async def get_templates(key: str, actor: CurrentActor, service: Service) -> ServiceTemplates:
    return await service.templates(actor, key)


@router.put("/types/{key}/templates", response_model=ServiceTemplates, responses=ERRORS)
async def update_templates(
    key: str, body: TemplateUpdate, actor: CurrentActor, service: Service
) -> ServiceTemplates:
    """`services.templates.manage`. The full template; tasks left out are retired."""
    return await service.update_templates(actor, key, body)


@router.get("", response_model=ServicesOverview, responses=AUTH_ERROR_RESPONSES)
async def list_services(
    *,
    actor: CurrentActor,
    service: Service,
    kind: Annotated[ServiceKind | None, Query()] = None,
    status_filter: Annotated[ServiceStatus | None, Query(alias="status")] = None,
    client_id: Annotated[uuid.UUID | None, Query()] = None,
) -> ServicesOverview:
    """Client services the actor can see, with tiles (fees only for money roles)."""
    return await service.overview(actor, kind=kind, status=status_filter, client_id=client_id)


@router.post(
    "/clients/{client_id}",
    status_code=status.HTTP_201_CREATED,
    response_model=list[ServiceItem],
    responses=ERRORS,
)
async def add_client_services(
    client_id: uuid.UUID, body: AddServices, actor: CurrentActor, service: Service
) -> list[ServiceItem]:
    """`services.manage` (the client's Account Manager). Returns the client's services."""
    return await service.add_services(actor, client_id, body.services)


@router.get("/{service_id}", response_model=ServiceDetail, responses=ERRORS)
async def get_service(
    service_id: uuid.UUID, actor: CurrentActor, service: Service
) -> ServiceDetail:
    """The workspace: this month's tasks and history (retainers) or the delivery tasks."""
    return await service.get(actor, service_id)


@router.get("/{service_id}/start-options", response_model=StartOptions, responses=ERRORS)
async def start_options(
    service_id: uuid.UUID, actor: CurrentActor, service: Service
) -> StartOptions:
    """Project Managers, with the delivering department's default."""
    return await service.start_options(actor, service_id)


@router.post("/{service_id}/start", response_model=ServiceDetail, responses=ERRORS)
async def start_service(
    service_id: uuid.UUID, body: StartService, actor: CurrentActor, service: Service
) -> ServiceDetail:
    """After onboarding: creates the delivery project with its template tasks."""
    return await service.start(actor, service_id, body)


@router.post("/{service_id}/generate", response_model=GenerateResult, responses=ERRORS)
async def generate_month(
    service_id: uuid.UUID, actor: CurrentActor, service: Service
) -> GenerateResult:
    """This month's retainer tasks. Idempotent: running it again creates nothing new."""
    return await service.generate(actor, service_id)


def _transition(action: str) -> Any:
    async def endpoint(
        service_id: uuid.UUID, actor: CurrentActor, service: Service
    ) -> ServiceDetail:
        return await service.transition(actor, service_id, action)

    endpoint.__name__ = f"{action}_service"
    return endpoint


for _action in ("pause", "resume", "complete", "cancel"):
    router.add_api_route(
        f"/{{service_id}}/{_action}",
        _transition(_action),
        methods=["POST"],
        response_model=ServiceDetail,
        responses=ERRORS,
        summary=f"{_action.capitalize()} a service",
    )
