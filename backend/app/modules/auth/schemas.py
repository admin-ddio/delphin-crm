"""Request/response models for the auth module (Firebase identity, ADR-0009)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from app.authz.actor import Actor


class SessionRequest(BaseModel):
    """Exchange a Firebase ID token (from the browser SDK) for an app session."""

    id_token: str = Field(min_length=20, max_length=8192)


class RegisterRequest(BaseModel):
    """Self sign-up: the Firebase account was just created in the browser."""

    id_token: str = Field(min_length=20, max_length=8192)
    full_name: str = Field(min_length=1, max_length=200)


class CurrentUser(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    roles: list[str]
    permissions: list[str]

    @classmethod
    def from_actor(cls, actor: Actor) -> CurrentUser:
        return cls(
            id=actor.user_id,
            email=actor.email,
            full_name=actor.full_name,
            roles=sorted(actor.roles),
            permissions=sorted(actor.permissions),
        )


class Message(BaseModel):
    message: str
