"""Request/response models for the clients module."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, EmailStr, Field

ClientStatus = Literal["contract_pending", "onboarding", "active"]


def _blank_to_none(value: object) -> object:
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


OptionalText = Annotated[str | None, BeforeValidator(_blank_to_none)]
OptionalEmail = Annotated[EmailStr | None, BeforeValidator(_blank_to_none)]


class ClientCreate(BaseModel):
    name: Annotated[str, BeforeValidator(lambda v: v.strip() if isinstance(v, str) else v)] = Field(
        min_length=1, max_length=200, description="Legal / business name"
    )
    website: OptionalText = Field(default=None, max_length=300)
    industry: OptionalText = Field(default=None, max_length=120)
    contact_name: OptionalText = Field(default=None, max_length=200)
    contact_email: OptionalEmail = None
    account_manager_id: uuid.UUID
    confirm_different_business: bool = Field(
        default=False,
        description="Override the similar-name warning (never overrides a duplicate domain).",
    )


class ClientUpdate(BaseModel):
    """PATCH: only fields present are changed."""

    name: Annotated[
        str | None, BeforeValidator(lambda v: v.strip() if isinstance(v, str) else v)
    ] = Field(default=None, min_length=1, max_length=200)
    website: OptionalText = Field(default=None, max_length=300)
    industry: OptionalText = Field(default=None, max_length=120)
    contact_name: OptionalText = Field(default=None, max_length=200)
    contact_email: OptionalEmail = None
    account_manager_id: uuid.UUID | None = None
    confirm_different_business: bool = False


class UserRef(BaseModel):
    id: uuid.UUID
    full_name: str


class ClientListItem(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    domain: str | None
    status: ClientStatus
    status_label: str
    account_manager: UserRef
    created_at: datetime


class ClientDetail(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    website: str | None
    domain: str | None
    industry: str | None
    contact_name: str | None
    contact_email: str | None
    status: ClientStatus
    status_label: str
    account_manager: UserRef
    created_at: datetime
    updated_at: datetime
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
