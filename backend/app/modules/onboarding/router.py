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
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.dependencies import CurrentActor
from app.core.clock import Clock, get_clock
from app.core.config import Settings, get_app_settings
from app.core.errors import AUTH_ERROR_RESPONSES, ErrorEnvelope
from app.db.session import get_session
from app.modules.onboarding.schemas import (
    AccessUpdate,
    AnswersIn,
    BoardRow,
    ContractAction,
    KickoffAction,
    KpiConfirmation,
    KpiIn,
    OnboardingDetail,
    PublicQuestionnaire,
    QuestionnaireLinkOut,
    TeamMemberIn,
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


# ---------------------------------------------------------------- step 1


@router.post("/clients/{client_id}/contract", response_model=OnboardingDetail, responses=ERRORS)
async def contract(
    client_id: ClientId, body: ContractAction, actor: CurrentActor, service: Service
) -> OnboardingDetail:
    return await service.contract(actor, client_id, body.action)


# ---------------------------------------------------------------- steps 4–5


@router.post(
    "/clients/{client_id}/questionnaire/send",
    response_model=QuestionnaireLinkOut,
    responses=ERRORS,
)
async def send_questionnaire(
    client_id: ClientId, actor: CurrentActor, service: Service
) -> QuestionnaireLinkOut:
    """Create a single-use link (30 days) for the client; replaces any earlier link."""
    return await service.send_questionnaire(actor, client_id)


@router.post(
    "/clients/{client_id}/questionnaire/answers",
    response_model=OnboardingDetail,
    responses=ERRORS,
)
async def record_answers(
    client_id: ClientId, body: AnswersIn, actor: CurrentActor, service: Service
) -> OnboardingDetail:
    """Record the client's answers on their behalf (e.g. collected on a call)."""
    return await service.record_answers(actor, client_id, body.answers)


# ---------------------------------------------------------------- steps 6–7


@router.patch(
    "/clients/{client_id}/access/{key}", response_model=OnboardingDetail, responses=ERRORS
)
async def update_access(
    client_id: ClientId,
    key: Annotated[str, Path(max_length=20)],
    body: AccessUpdate,
    actor: CurrentActor,
    service: Service,
) -> OnboardingDetail:
    return await service.update_access(actor, client_id, key, body.status)


@router.post(
    "/clients/{client_id}/access/receive-all", response_model=OnboardingDetail, responses=ERRORS
)
async def receive_all_access(
    client_id: ClientId, actor: CurrentActor, service: Service
) -> OnboardingDetail:
    return await service.receive_all(actor, client_id)


# ---------------------------------------------------------------- step 8


@router.post("/clients/{client_id}/kpis", response_model=OnboardingDetail, responses=ERRORS)
async def add_kpi(
    client_id: ClientId, body: KpiIn, actor: CurrentActor, service: Service
) -> OnboardingDetail:
    return await service.add_kpi(actor, client_id, body)


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
    """Record that the client confirmed every pending KPI target (who, and how)."""
    return await service.confirm_kpis(actor, client_id, body)


# ---------------------------------------------------------------- steps 9–10


@router.post(
    "/clients/{client_id}/kickoffs/{kind}", response_model=OnboardingDetail, responses=ERRORS
)
async def kickoff(
    client_id: ClientId,
    kind: Literal["client", "internal"],
    body: KickoffAction,
    actor: CurrentActor,
    service: Service,
) -> OnboardingDetail:
    return await service.kickoff(actor, client_id, kind, body)


@router.get("/clients/{client_id}/team/options", response_model=list[UserRef], responses=ERRORS)
async def team_options(client_id: ClientId, actor: CurrentActor, service: Service) -> list[UserRef]:
    """People who can be added to this client's team."""
    return await service.team_options(actor, client_id)


@router.post("/clients/{client_id}/team", response_model=OnboardingDetail, responses=ERRORS)
async def add_team_member(
    client_id: ClientId, body: TeamMemberIn, actor: CurrentActor, service: Service
) -> OnboardingDetail:
    return await service.add_team_member(actor, client_id, body.user_id)


@router.delete(
    "/clients/{client_id}/team/{user_id}", response_model=OnboardingDetail, responses=ERRORS
)
async def remove_team_member(
    client_id: ClientId, user_id: uuid.UUID, actor: CurrentActor, service: Service
) -> OnboardingDetail:
    return await service.remove_team_member(actor, client_id, user_id)


# ---------------------------------------------------------------- steps 11–12


@router.post("/clients/{client_id}/review", response_model=OnboardingDetail, responses=ERRORS)
async def pass_review(
    client_id: ClientId, actor: CurrentActor, service: Service
) -> OnboardingDetail:
    """Passes only when steps 1–10 are done."""
    return await service.review(actor, client_id)


@router.post("/clients/{client_id}/complete", response_model=OnboardingDetail, responses=ERRORS)
async def complete_onboarding(
    client_id: ClientId, actor: CurrentActor, service: Service
) -> OnboardingDetail:
    """Re-checks access, KPI confirmation and steps 1–11; the client becomes Active."""
    return await service.complete(actor, client_id)


# ---------------------------------------------------------------- public questionnaire


@router.get("/questionnaire/{token}", response_model=PublicQuestionnaire, responses=PUBLIC_ERRORS)
async def public_questionnaire(
    token: Annotated[str, Path(min_length=16, max_length=200)], service: Service
) -> PublicQuestionnaire:
    """No sign-in: the single-use link token is the credential."""
    return await service.public_questionnaire(token)


@router.post(
    "/questionnaire/{token}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses=PUBLIC_ERRORS,
)
async def submit_public_questionnaire(
    token: Annotated[str, Path(min_length=16, max_length=200)],
    body: AnswersIn,
    service: Service,
) -> None:
    await service.submit_public_questionnaire(token, body.answers)
