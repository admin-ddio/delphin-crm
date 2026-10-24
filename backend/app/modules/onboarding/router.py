"""HTTP surface of the onboarding module.

Staff endpoints live under /onboarding/clients/{client_id}/…; every mutation
returns the full OnboardingDetail so the UI always shows the server's state.
The public questionnaire (/onboarding/questionnaire/{token}) needs no sign-in:
the single-use token is the credential.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Path, Response, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.dependencies import CurrentActor
from app.core.clock import Clock, get_clock
from app.core.config import Settings, get_app_settings
from app.core.errors import AUTH_ERROR_RESPONSES, ErrorEnvelope
from app.db.session import get_session
from app.modules.onboarding.schemas import (
    AccessDetails,
    AccessItemIn,
    AccessUpdate,
    AnswersIn,
    BoardRow,
    KpiConfirmation,
    KpiIn,
    KpiNotesIn,
    KpiUpdate,
    OnboardingDetail,
    PublicQuestionnaire,
    QuestionnaireLinkOut,
    TeamMemberIn,
    TeamMemberUpdate,
    UserRef,
)
from app.modules.onboarding.service import OnboardingService

TAG = {
    "name": "onboarding",
    "description": "Client onboarding workflow (13 steps) and public questionnaire",
}

router = APIRouter(prefix="/onboarding", tags=["onboarding"])

ERRORS: dict[int | str, dict[str, Any]] = {
    **AUTH_ERROR_RESPONSES,
    404: {"model": ErrorEnvelope, "description": "Client not found or not visible"},
    409: {"model": ErrorEnvelope, "description": "Conflict"},
    422: {"model": ErrorEnvelope, "description": "Validation failed or business rule violated"},
}
PUBLIC_ERRORS: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorEnvelope, "description": "Link invalid, used or expired"},
    422: {"model": ErrorEnvelope, "description": "Missing answers"},
}

ClientId = Annotated[uuid.UUID, Path()]


class BulkAccess(BaseModel):
    status: Literal["requested", "received"]


def get_onboarding_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    clock: Annotated[Clock, Depends(get_clock)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> OnboardingService:
    return OnboardingService(session, clock=clock, settings=settings)


Service = Annotated[OnboardingService, Depends(get_onboarding_service)]


# ---------------------------------------------------------------- board & detail


@router.get("", response_model=list[BoardRow], responses=AUTH_ERROR_RESPONSES)
async def onboarding_board(actor: CurrentActor, service: Service) -> list[BoardRow]:
    """Every visible client's onboarding progress; unfinished first."""
    return await service.board(actor)


@router.get("/clients/{client_id}", response_model=OnboardingDetail, responses=ERRORS)
async def get_onboarding(
    client_id: ClientId, actor: CurrentActor, service: Service
) -> OnboardingDetail:
    return await service.detail(actor, client_id)


# ---------------------------------------------------------------- questionnaire


@router.post(
    "/clients/{client_id}/questionnaire/send",
    response_model=QuestionnaireLinkOut,
    responses=ERRORS,
)
async def send_questionnaire(
    client_id: ClientId, actor: CurrentActor, service: Service
) -> QuestionnaireLinkOut:
    """Create a single-use link (30 days); any earlier link stops working."""
    return await service.send_questionnaire(actor, client_id)


@router.put("/clients/{client_id}/questionnaire", response_model=OnboardingDetail, responses=ERRORS)
async def save_questionnaire_draft(
    client_id: ClientId, body: AnswersIn, actor: CurrentActor, service: Service
) -> OnboardingDetail:
    """Save the answers as a draft (partial answers allowed)."""
    return await service.save_answers(actor, client_id, body.answers, submit=False)


@router.post(
    "/clients/{client_id}/questionnaire/submit",
    response_model=OnboardingDetail,
    responses=ERRORS,
)
async def submit_questionnaire(
    client_id: ClientId, body: AnswersIn, actor: CurrentActor, service: Service
) -> OnboardingDetail:
    """Record the client's answers (every required answer is needed)."""
    return await service.save_answers(actor, client_id, body.answers, submit=True)


@router.get("/questionnaire/{token}", response_model=PublicQuestionnaire, responses=PUBLIC_ERRORS)
async def public_questionnaire(token: str, service: Service) -> PublicQuestionnaire:
    """Public: the client opens the link (no sign-in)."""
    return await service.public_questionnaire(token)


@router.put("/questionnaire/{token}", response_model=PublicQuestionnaire, responses=PUBLIC_ERRORS)
async def save_public_draft(token: str, body: AnswersIn, service: Service) -> PublicQuestionnaire:
    """Public: save a draft and come back later with the same link."""
    return await service.save_public_draft(token, body.answers)


@router.post(
    "/questionnaire/{token}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses=PUBLIC_ERRORS,
)
async def submit_public_questionnaire(token: str, body: AnswersIn, service: Service) -> None:
    """Public: submit the answers; the link is used up."""
    await service.submit_public_questionnaire(token, body.answers)


# ---------------------------------------------------------------- access


@router.patch(
    "/clients/{client_id}/access/{key}", response_model=OnboardingDetail, responses=ERRORS
)
async def update_access(
    client_id: ClientId, key: str, body: AccessUpdate, actor: CurrentActor, service: Service
) -> OnboardingDetail:
    return await service.update_access(actor, client_id, key, body.status)


@router.post("/clients/{client_id}/access/bulk", response_model=OnboardingDetail, responses=ERRORS)
async def bulk_access(
    client_id: ClientId, body: BulkAccess, actor: CurrentActor, service: Service
) -> OnboardingDetail:
    """Request every pending item, or mark every pending/requested item received."""
    return await service.bulk_access(actor, client_id, body.status)


@router.post("/clients/{client_id}/access", response_model=OnboardingDetail, responses=ERRORS)
async def add_access_item(
    client_id: ClientId, body: AccessItemIn, actor: CurrentActor, service: Service
) -> OnboardingDetail:
    return await service.add_access_item(actor, client_id, body)


@router.patch(
    "/clients/{client_id}/access/{key}/details",
    response_model=OnboardingDetail,
    responses=ERRORS,
)
async def update_access_details(
    client_id: ClientId, key: str, body: AccessDetails, actor: CurrentActor, service: Service
) -> OnboardingDetail:
    return await service.update_access_details(actor, client_id, key, body)


@router.delete(
    "/clients/{client_id}/access/{key}", response_model=OnboardingDetail, responses=ERRORS
)
async def delete_access_item(
    client_id: ClientId, key: str, actor: CurrentActor, service: Service
) -> OnboardingDetail:
    """Custom items only."""
    return await service.delete_access_item(actor, client_id, key)


# ---------------------------------------------------------------- KPIs


@router.post("/clients/{client_id}/kpis", response_model=OnboardingDetail, responses=ERRORS)
async def add_kpi(
    client_id: ClientId, body: KpiIn, actor: CurrentActor, service: Service
) -> OnboardingDetail:
    return await service.add_kpi(actor, client_id, body)


@router.patch(
    "/clients/{client_id}/kpis/{kpi_id}", response_model=OnboardingDetail, responses=ERRORS
)
async def update_kpi(
    client_id: ClientId,
    kpi_id: uuid.UUID,
    body: KpiUpdate,
    actor: CurrentActor,
    service: Service,
) -> OnboardingDetail:
    """Changing a confirmed target clears its confirmation; current values any time."""
    return await service.update_kpi(actor, client_id, kpi_id, body)


@router.delete(
    "/clients/{client_id}/kpis/{kpi_id}", response_model=OnboardingDetail, responses=ERRORS
)
async def delete_kpi(
    client_id: ClientId, kpi_id: uuid.UUID, actor: CurrentActor, service: Service
) -> OnboardingDetail:
    return await service.delete_kpi(actor, client_id, kpi_id)


@router.post("/clients/{client_id}/kpis/confirm", response_model=OnboardingDetail, responses=ERRORS)
async def confirm_kpis(
    client_id: ClientId, body: KpiConfirmation, actor: CurrentActor, service: Service
) -> OnboardingDetail:
    return await service.confirm_kpis(actor, client_id, body)


@router.put("/clients/{client_id}/kpi-notes", response_model=OnboardingDetail, responses=ERRORS)
async def kpi_notes(
    client_id: ClientId, body: KpiNotesIn, actor: CurrentActor, service: Service
) -> OnboardingDetail:
    return await service.kpi_notes(actor, client_id, body)


# ---------------------------------------------------------------- team


@router.get("/clients/{client_id}/team/options", response_model=list[UserRef], responses=ERRORS)
async def team_options(client_id: ClientId, actor: CurrentActor, service: Service) -> list[UserRef]:
    return await service.team_options(actor, client_id)


@router.post("/clients/{client_id}/team", response_model=OnboardingDetail, responses=ERRORS)
async def add_team_member(
    client_id: ClientId, body: TeamMemberIn, actor: CurrentActor, service: Service
) -> OnboardingDetail:
    return await service.add_team_member(actor, client_id, body)


@router.patch(
    "/clients/{client_id}/team/{user_id}", response_model=OnboardingDetail, responses=ERRORS
)
async def update_team_member(
    client_id: ClientId,
    user_id: uuid.UUID,
    body: TeamMemberUpdate,
    actor: CurrentActor,
    service: Service,
) -> OnboardingDetail:
    return await service.update_team_member(actor, client_id, user_id, body)


@router.delete(
    "/clients/{client_id}/team/{user_id}", response_model=OnboardingDetail, responses=ERRORS
)
async def remove_team_member(
    client_id: ClientId, user_id: uuid.UUID, actor: CurrentActor, service: Service
) -> OnboardingDetail:
    return await service.remove_team_member(actor, client_id, user_id)


# ---------------------------------------------------------------- review & completion


@router.post("/clients/{client_id}/review", response_model=OnboardingDetail, responses=ERRORS)
async def review(client_id: ClientId, actor: CurrentActor, service: Service) -> OnboardingDetail:
    return await service.review(actor, client_id)


@router.post("/clients/{client_id}/complete", response_model=OnboardingDetail, responses=ERRORS)
async def complete(client_id: ClientId, actor: CurrentActor, service: Service) -> OnboardingDetail:
    return await service.complete(actor, client_id)
