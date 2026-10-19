"""The real Firebase Admin SDK against the Auth Emulator (skipped without it)."""

from __future__ import annotations

import os
import uuid

import httpx
import pytest

from app.platform.identity.firebase import FirebaseIdentityProvider, InvalidIdentityTokenError

EMULATOR = os.environ.get("FIREBASE_AUTH_EMULATOR_HOST")
PROJECT = os.environ.get("FIREBASE_PROJECT_ID", "demo-delphin")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not EMULATOR, reason="FIREBASE_AUTH_EMULATOR_HOST not set"),
]


async def emulator_sign_up(email: str, password: str) -> str:
    """Create an account through the emulator's public REST API; returns its ID token."""
    url = f"http://{EMULATOR}/identitytoolkit.googleapis.com/v1/accounts:signUp?key=demo-api-key"
    async with httpx.AsyncClient() as http:
        response = await http.post(
            url, json={"email": email, "password": password, "returnSecureToken": True}
        )
    response.raise_for_status()
    token: str = response.json()["idToken"]
    return token


async def test_verifies_emulator_tokens_and_reports_verification() -> None:
    provider = FirebaseIdentityProvider(PROJECT)
    email = f"emu-{uuid.uuid4().hex[:8]}@example.com"
    claims = await provider.verify_id_token(await emulator_sign_up(email, "emulator-password"))
    assert claims.email == email
    assert claims.email_verified is False  # self sign-up: not verified yet
    assert claims.uid


async def test_rejects_garbage_tokens() -> None:
    with pytest.raises(InvalidIdentityTokenError):
        await FirebaseIdentityProvider(PROJECT).verify_id_token("x" * 40)


async def test_invitation_user_and_setup_link() -> None:
    provider = FirebaseIdentityProvider(PROJECT)
    email = f"invite-{uuid.uuid4().hex[:8]}@example.com"
    uid = await provider.ensure_user(email, "Invited Person")
    assert await provider.ensure_user(email, "Invited Person") == uid  # idempotent
    link = await provider.password_setup_link(email, "http://localhost:5173/login")
    assert "oobCode=" in link
    assert "mode=resetPassword" in link


async def test_email_verified_and_delete() -> None:
    provider = FirebaseIdentityProvider(PROJECT)
    email = f"del-{uuid.uuid4().hex[:8]}@example.com"
    uid = await provider.ensure_user(email, "Delete Me")
    assert await provider.email_verified(uid) is False
    await provider.delete_user(uid)
    assert await provider.email_verified(uid) is None
    await provider.delete_user(uid)  # already gone: no error
