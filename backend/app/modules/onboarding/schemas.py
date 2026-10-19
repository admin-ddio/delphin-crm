"""Request/response models for the onboarding module."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, Field

StepState = Literal["todo", "progress", "done", "blocked"]
OverallStatus = Literal["in_progress", "blocked", "completed"]
AccessStatus = Literal["pending", "requested", "received", "verified", "rejected", "not_required"]
ContactChannel = Literal["email", "call", "meeting", "whatsapp"]


def _strip(value: object) -> object:
    return value.strip() if isinstance(value, str) else value


Text = Annotated[str, BeforeValidator(_strip)]


class UserRef(BaseModel):
    id: uuid.UUID
    full_name: str


class StepOut(BaseModel):
    number: int
    key: str
    label: str
    hint: str
    state: StepState
    detail: str


class AccessItemOut(BaseModel):
    key: str
    label: str
    status: AccessStatus
    verified_by: UserRef | None
    verified_at: datetime | None


class KpiOut(BaseModel):
    id: uuid.UUID
    metric: str
    baseline: Decimal
    target: Decimal
    unit: str
    confirmed_by_name: str | None
    confirmed_via: str | None
    confirmed_at: datetime | None


class QuestionOut(BaseModel):
    key: str
    label: str
    answer: str | None


class KickoffOut(BaseModel):
    status: Literal["none", "scheduled", "done"]
    at: datetime | None
    notes: str | None


class Permissions(BaseModel):
    manage: bool
    verify_access: bool
    confirm_kpis: bool


class OnboardingDetail(BaseModel):
    client_id: uuid.UUID
    client_name: str
    client_code: str
    status: OverallStatus
    progress: int
    steps: list[StepOut]
    contract: Literal["none", "draft", "signed"]
    contract_signed_at: datetime | None
    questionnaire: Literal["none", "sent", "submitted"]
    questionnaire_sent_at: datetime | None
    questionnaire_submitted_at: datetime | None
    questions: list[QuestionOut]
    access: list[AccessItemOut]
    kpis: list[KpiOut]
    kickoff_client: KickoffOut
    kickoff_internal: KickoffOut
    team: list[UserRef]
    reviewed_at: datetime | None
    completed_at: datetime | None
    permissions: Permissions


class QuestionnaireLinkOut(BaseModel):
    """The raw link is shown once, to the person who created it."""

    url: str
    expires_at: datetime
    onboarding: OnboardingDetail


class BoardRow(BaseModel):
    client_id: uuid.UUID
    client_name: str
    client_code: str
    status: OverallStatus
    progress: int
    current_step: str | None
    current_detail: str | None
    account_manager: UserRef


# ---------------------------------------------------------------- requests


class ContractAction(BaseModel):
    action: Literal["record", "sign"]


class AnswersIn(BaseModel):
    answers: dict[str, Annotated[str, Field(max_length=4000)]] = Field(
        description="Question key → answer. Every question needs an answer."
    )


class AccessUpdate(BaseModel):
    status: AccessStatus


class KpiIn(BaseModel):
    metric: Text = Field(min_length=1, max_length=120)
    baseline: Decimal = Field(max_digits=18, decimal_places=4)
    target: Decimal = Field(max_digits=18, decimal_places=4)
    unit: Text = Field(min_length=1, max_length=60)


class KpiConfirmation(BaseModel):
    confirmed_by: Text = Field(min_length=1, max_length=200, description="Who at the client")
    via: ContactChannel


class KickoffAction(BaseModel):
    action: Literal["schedule", "complete"]
    at: datetime | None = Field(default=None, description="Meeting date/time (schedule)")
    notes: Annotated[str | None, BeforeValidator(_strip)] = Field(default=None, max_length=4000)


class TeamMemberIn(BaseModel):
    user_id: uuid.UUID


class PublicQuestionnaire(BaseModel):
    client_name: str
    questions: list[QuestionOut]
