"""Request/response models for the clients module (create form from the product mockups)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, EmailStr, Field, model_validator

from app.modules.services.schemas import ServiceSelection

ClientStatus = Literal["onboarding", "active", "on_hold", "completed"]
BusinessType = Literal["b2b", "b2c", "b2b_b2c", "d2c", "non_profit", "government"]
CompanySize = Literal["1-10", "11-50", "51-200", "201-500", "501-1000", "1000+"]
PaymentTerms = Literal["monthly", "quarterly", "half_yearly", "annually", "one_time", "milestone"]


def _blank_to_none(value: object) -> object:
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


def _strip(value: object) -> object:
    return value.strip() if isinstance(value, str) else value


OptionalText = Annotated[str | None, BeforeValidator(_blank_to_none)]
OptionalEmail = Annotated[EmailStr | None, BeforeValidator(_blank_to_none)]
RequiredText = Annotated[str, BeforeValidator(_strip)]
Phone = Annotated[str | None, BeforeValidator(_blank_to_none)]
Country = Annotated[str, BeforeValidator(lambda v: v.strip().upper() if isinstance(v, str) else v)]


class _ContractDates(BaseModel):
    @model_validator(mode="after")
    def _end_after_start(self) -> _ContractDates:
        start = getattr(self, "contract_start", None)
        end = getattr(self, "contract_end", None)
        if start and end and end < start:
            msg = "The contract end date must be on or after the start date."
            raise ValueError(msg)
        return self


class ClientCreate(_ContractDates):
    # Company information
    name: RequiredText = Field(min_length=1, max_length=200, description="Company name")
    website: OptionalText = Field(default=None, max_length=300)
    industry: RequiredText = Field(min_length=1, max_length=120)
    business_type: BusinessType | None = None
    company_size: CompanySize | None = None
    country: Country = Field(default="IN", pattern=r"^[A-Z]{2}$", description="ISO 3166-1 alpha-2")
    description: OptionalText = Field(default=None, max_length=500)
    # Primary contact
    contact_name: RequiredText = Field(min_length=1, max_length=200)
    contact_designation: RequiredText = Field(min_length=1, max_length=120)
    contact_email: EmailStr
    contact_phone: Annotated[str, BeforeValidator(_strip)] = Field(min_length=5, max_length=40)
    contact_alt_email: OptionalEmail = None
    contact_alt_phone: Phone = Field(default=None, max_length=40)
    # Contract (onboarding step 1: captured at creation)
    contract_start: date
    contract_end: date
    contract_value: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    payment_terms: PaymentTerms | None = None
    contract_notes: OptionalText = Field(default=None, max_length=250)
    # Account Manager
    account_manager_id: uuid.UUID
    # Services bought (retainers: SEO, Social Media; projects: Website, Web App, Mobile App)
    services: list[ServiceSelection] = Field(min_length=1, max_length=10)
    confirm_different_business: bool = Field(
        default=False,
        description="Override the similar-name warning (never overrides a duplicate domain).",
    )


class ClientUpdate(_ContractDates):
    """PATCH: only fields present are changed; required fields can't be cleared."""

    name: OptionalText = Field(default=None, min_length=1, max_length=200)
    website: OptionalText = Field(default=None, max_length=300)
    industry: OptionalText = Field(default=None, max_length=120)
    business_type: BusinessType | None = None
    company_size: CompanySize | None = None
    country: Annotated[str | None, BeforeValidator(_blank_to_none)] = Field(
        default=None, pattern=r"^[A-Z]{2}$"
    )
    description: OptionalText = Field(default=None, max_length=500)
    contact_name: OptionalText = Field(default=None, max_length=200)
    contact_designation: OptionalText = Field(default=None, max_length=120)
    contact_email: OptionalEmail = None
    contact_phone: Phone = Field(default=None, max_length=40)
    contact_alt_email: OptionalEmail = None
    contact_alt_phone: Phone = Field(default=None, max_length=40)
    contract_start: date | None = None
    contract_end: date | None = None
    contract_value: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    payment_terms: PaymentTerms | None = None
    contract_notes: OptionalText = Field(default=None, max_length=250)
    account_manager_id: uuid.UUID | None = None
    confirm_different_business: bool = False


class StatusChange(BaseModel):
    """hold: Onboarding/Active → On hold. complete: Active/On hold → Completed.
    reactivate: On hold/Completed → Onboarding or Active (by onboarding state)."""

    action: Literal["hold", "complete", "reactivate"]


class UserRef(BaseModel):
    id: uuid.UUID
    full_name: str


class ClientListItem(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    website: str | None
    domain: str | None
    industry: str | None
    status: ClientStatus
    status_label: str
    account_manager: UserRef
    created_at: datetime
    #: Latest event on the client's activity timeline.
    last_activity_at: datetime | None


class StatusCounts(BaseModel):
    all: int
    onboarding: int
    active: int
    on_hold: int
    completed: int


class ClientDetail(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    website: str | None
    domain: str | None
    industry: str | None
    business_type: BusinessType | None
    company_size: CompanySize | None
    country: str | None
    description: str | None
    contact_name: str | None
    contact_designation: str | None
    contact_email: str | None
    contact_phone: str | None
    contact_alt_email: str | None
    contact_alt_phone: str | None
    contract_start: date | None
    contract_end: date | None
    contract_value: Decimal | None
    contract_currency: str
    payment_terms: PaymentTerms | None
    contract_notes: str | None
    status: ClientStatus
    status_label: str
    account_manager: UserRef
    created_at: datetime
    updated_at: datetime
    last_activity_at: datetime | None
    can_edit: bool


class AccountManagerOption(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str


class ClientActivity(BaseModel):
    id: uuid.UUID
    occurred_at: datetime
    summary: str
    actor: UserRef | None
