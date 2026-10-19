"""Request/response models for the onboarding module (v2, product mockups 2026-10-19)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, Field, field_validator

StepState = Literal["todo", "progress", "done", "blocked"]
StageState = Literal["pending", "in_progress", "completed", "blocked"]
OverallStatus = Literal["in_progress", "blocked", "completed"]
AccessStatus = Literal["pending", "requested", "received", "verified", "rejected", "not_required"]
ContactChannel = Literal["email", "call", "meeting", "whatsapp"]
KpiStatus = Literal["not_measured", "on_track", "at_risk", "behind", "achieved"]
GoalKey = Literal[
    "organic_traffic",
    "leads",
    "sales",
    "brand_awareness",
    "reputation",
    "keywords",
    "new_markets",
    "engagement",
    "other",
]
ToneKey = Literal[
    "professional",
    "friendly",
    "authoritative",
    "conversational",
    "technical",
    "playful",
    "inspirational",
    "premium",
]
YesNo = Literal["yes", "no", "unsure"]
TeamArea = Literal[
    "account",
    "project_management",
    "seo",
    "content",
    "design",
    "development",
    "social",
    "analytics",
]


def _strip(value: object) -> object:
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


Text = Annotated[str | None, BeforeValidator(_strip)]
Required = Annotated[str, BeforeValidator(lambda v: v.strip() if isinstance(v, str) else v)]


class UserRef(BaseModel):
    id: uuid.UUID
    full_name: str


# ---------------------------------------------------------------- questionnaire answers


def _unique[T](values: list[T]) -> list[T]:
    return list(dict.fromkeys(values))


class BusinessGoals(BaseModel):
    goals: list[GoalKey] = Field(default_factory=list, max_length=9)
    other: Text = Field(default=None, max_length=200)
    details: Text = Field(default=None, max_length=2000)

    _dedupe = field_validator("goals")(_unique)


class TargetMarkets(BaseModel):
    locations: Text = Field(default=None, max_length=1000, description="Countries, regions, cities")
    audiences: Text = Field(default=None, max_length=2000)
    languages: Text = Field(default=None, max_length=200)


class Competitor(BaseModel):
    name: Text = Field(default=None, max_length=200)
    website: Text = Field(default=None, max_length=300)


class Competitors(BaseModel):
    competitors: list[Competitor] = Field(default_factory=list, max_length=10)
    notes: Text = Field(default=None, max_length=2000)


class BrandVoice(BaseModel):
    tones: list[ToneKey] = Field(default_factory=list, max_length=8)
    guidelines: Text = Field(default=None, max_length=2000)
    avoid: Text = Field(default=None, max_length=1000, description="Words or topics to avoid")

    _dedupe = field_validator("tones")(_unique)


class PastSeo(BaseModel):
    worked_before: YesNo | None = None
    details: Text = Field(default=None, max_length=2000)
    penalties: YesNo | None = None
    tools: Text = Field(default=None, max_length=500)


class Additional(BaseModel):
    products_services: Text = Field(default=None, max_length=2000)
    notes: Text = Field(default=None, max_length=2000)


class Answers(BaseModel):
    business_goals: BusinessGoals = Field(default_factory=BusinessGoals)
    target_markets: TargetMarkets = Field(default_factory=TargetMarkets)
    competitors: Competitors = Field(default_factory=Competitors)
    brand_voice: BrandVoice = Field(default_factory=BrandVoice)
    past_seo: PastSeo = Field(default_factory=PastSeo)
    additional: Additional = Field(default_factory=Additional)


class Choice(BaseModel):
    key: str
    label: str


class SectionOut(BaseModel):
    key: str
    label: str
    question: str
    complete: bool
    missing: list[str]


class QuestionnaireForm(BaseModel):
    """Everything the wizard needs: sections with completeness, choices, answers."""

    sections: list[SectionOut]
    goals: list[Choice]
    tones: list[Choice]
    answers: Answers


class QuestionnaireOut(QuestionnaireForm):
    status: Literal["none", "sent", "submitted"]
    sent_at: datetime | None
    submitted_at: datetime | None
    source: Literal["client", "staff"] | None
    updated_at: datetime | None


# ---------------------------------------------------------------- detail sections


class StepOut(BaseModel):
    number: int
    key: str
    label: str
    hint: str
    state: StepState
    detail: str


class StageOut(BaseModel):
    key: str
    label: str
    state: StageState


class NextActionOut(BaseModel):
    step: str
    title: str
    detail: str
    due: date
    priority: Literal["high", "medium", "low"]


class QuickStatus(BaseModel):
    key: str
    label: str
    state: Literal["pending", "in_progress", "completed", "blocked"]


class AccessItemOut(BaseModel):
    key: str
    label: str
    description: str | None
    status: AccessStatus
    is_custom: bool
    requested_at: datetime | None
    received_at: datetime | None
    verified_by: UserRef | None
    verified_at: datetime | None
    notes: str | None


class AccessSummary(BaseModel):
    required: int
    verified: int
    percent: int


class KpiOut(BaseModel):
    id: uuid.UUID
    metric: str
    description: str | None
    baseline: Decimal
    target: Decimal
    unit: str
    target_date: date | None
    current_value: Decimal | None
    progress: int | None
    status: KpiStatus
    confirmed_by_name: str | None
    confirmed_via: str | None
    confirmed_at: datetime | None


class KpiSummary(BaseModel):
    total: int
    on_track: int
    at_risk: int
    behind: int
    achieved: int
    not_measured: int
    #: Average progress of measured KPIs (0–100), None when none is measured.
    overall: int | None
    notes: str | None
    notes_by: UserRef | None
    notes_at: datetime | None
    #: Set when every KPI is confirmed: who at the client, how, when (latest).
    confirmed_by: str | None
    confirmed_via: str | None
    confirmed_at: datetime | None


class KickoffOut(BaseModel):
    """Derived from meetings: a completed meeting of the type completes the step."""

    state: Literal["none", "scheduled", "done"]
    meeting_id: uuid.UUID | None
    at: datetime | None


class TeamMemberOut(BaseModel):
    user: UserRef
    email: str
    role: str | None
    area: TeamArea | None
    role_title: str | None
    responsibilities: str | None
    allocation: int | None
    added_at: datetime


class CoverageOut(BaseModel):
    area: TeamArea
    label: str
    members: list[UserRef]
    required: bool


class Permissions(BaseModel):
    manage: bool
    verify_access: bool
    confirm_kpis: bool
    schedule_meetings: bool
    upload_documents: bool


class ClientSummary(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    status: Literal["onboarding", "active", "on_hold", "completed"]
    account_manager: UserRef
    created_at: datetime


class OnboardingDetail(BaseModel):
    client: ClientSummary
    status: OverallStatus
    progress: int
    steps: list[StepOut]
    stages: list[StageOut]
    next_actions: list[NextActionOut]
    quick_status: list[QuickStatus]
    questionnaire: QuestionnaireOut
    access: list[AccessItemOut]
    access_summary: AccessSummary
    kpis: list[KpiOut]
    kpi_summary: KpiSummary
    kickoff_client: KickoffOut
    kickoff_internal: KickoffOut
    team: list[TeamMemberOut]
    coverage: list[CoverageOut]
    documents: int
    contract_documents: int
    reviewed_at: datetime | None
    completed_at: datetime | None
    #: Why nothing can change right now (e.g. the client is on hold).
    locked_reason: str | None
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
    client_status: Literal["onboarding", "active", "on_hold", "completed"]
    status: OverallStatus
    progress: int
    current_step: str | None
    current_detail: str | None
    account_manager: UserRef


class PublicQuestionnaire(QuestionnaireForm):
    client_name: str


# ---------------------------------------------------------------- requests


class AnswersIn(BaseModel):
    answers: Answers


class AccessUpdate(BaseModel):
    status: AccessStatus


class AccessItemIn(BaseModel):
    label: Required = Field(min_length=1, max_length=100)
    description: Text = Field(default=None, max_length=300)


class AccessDetails(BaseModel):
    description: Text = Field(default=None, max_length=300)
    notes: Text = Field(default=None, max_length=2000)


class KpiIn(BaseModel):
    metric: Required = Field(min_length=1, max_length=120)
    description: Text = Field(default=None, max_length=200)
    baseline: Decimal = Field(max_digits=18, decimal_places=4)
    target: Decimal = Field(max_digits=18, decimal_places=4)
    unit: Required = Field(min_length=1, max_length=60)
    target_date: date | None = None
    current_value: Decimal | None = Field(default=None, max_digits=18, decimal_places=4)


class KpiUpdate(BaseModel):
    metric: Text = Field(default=None, max_length=120)
    description: Text = Field(default=None, max_length=200)
    baseline: Decimal | None = Field(default=None, max_digits=18, decimal_places=4)
    target: Decimal | None = Field(default=None, max_digits=18, decimal_places=4)
    unit: Text = Field(default=None, max_length=60)
    target_date: date | None = None
    current_value: Decimal | None = Field(default=None, max_digits=18, decimal_places=4)


class KpiNotesIn(BaseModel):
    notes: Text = Field(default=None, max_length=2000)


class KpiConfirmation(BaseModel):
    confirmed_by: Required = Field(min_length=1, max_length=200, description="Who at the client")
    via: ContactChannel


class TeamMemberIn(BaseModel):
    user_id: uuid.UUID
    area: TeamArea | None = None
    role_title: Text = Field(default=None, max_length=100)
    responsibilities: Text = Field(default=None, max_length=2000)
    allocation: int | None = Field(default=None, ge=0, le=100, description="% of their time")


class TeamMemberUpdate(BaseModel):
    area: TeamArea | None = None
    role_title: Text = Field(default=None, max_length=100)
    responsibilities: Text = Field(default=None, max_length=2000)
    allocation: int | None = Field(default=None, ge=0, le=100)
