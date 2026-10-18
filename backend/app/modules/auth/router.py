"""HTTP surface of the auth module.

Passwords, verification and reset e-mails are handled by Firebase in the browser
(ADR-0009). The API exchanges a Firebase ID token for an app session and manages
that session.
"""

from __future__ import annotations

import ipaddress
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.dependencies import CurrentActor
from app.core.clock import Clock, get_clock
from app.core.config import Settings, get_app_settings
from app.core.errors import ErrorEnvelope, error_response
from app.core.security import clear_session_cookie, set_csrf_cookie, set_session_cookie
from app.db.session import get_session
from app.modules.auth.schemas import CurrentUser, Message, RegisterRequest, SessionRequest
from app.modules.auth.service import AuthService, RequestMeta, SignInFailure
from app.platform.identity.firebase import IdentityProvider, get_identity_provider

TAG = {
    "name": "auth",
    "description": "Sign-in (Firebase identity → app session), sessions, current user",
}

router = APIRouter(prefix="/auth", tags=["auth"])

SettingsDep = Annotated[Settings, Depends(get_app_settings)]

FAILURES: dict[SignInFailure, tuple[int, str, str]] = {
    "invalid_token": (
        401,
        "unauthorized",
        "Your sign-in could not be verified. Sign in again.",
    ),
    "email_not_verified": (
        403,
        "email_not_verified",
        "Verify your e-mail address before signing in. Check your inbox for the link.",
    ),
    "no_access": (
        403,
        "no_access",
        "This account doesn't have access to Delphin. Ask an administrator for an invitation.",
    ),
    "pending_approval": (
        403,
        "pending_approval",
        "Your account is waiting for approval by an administrator. "
        "You'll be able to sign in once it's approved.",
    ),
}

REGISTERED = (
    "Account created. Verify your e-mail with the link we sent, then wait for an "
    "administrator to approve your account."
)


def get_auth_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    clock: Annotated[Clock, Depends(get_clock)],
    settings: SettingsDep,
    identity: Annotated[IdentityProvider, Depends(get_identity_provider)],
) -> AuthService:
    return AuthService(session, clock=clock, settings=settings, identity=identity)


Service = Annotated[AuthService, Depends(get_auth_service)]


def request_meta(request: Request) -> RequestMeta:
    host = request.client.host if request.client else None
    try:
        ip = str(ipaddress.ip_address(host)) if host else None
    except ValueError:
        ip = None
    return RequestMeta(ip=ip, user_agent=request.headers.get("user-agent"))


@router.get("/csrf", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def issue_csrf_token(response: Response, settings: SettingsDep) -> None:
    """Set the CSRF cookie the SPA echoes back in the X-CSRF-Token header."""
    set_csrf_cookie(response, settings)


@router.post(
    "/session",
    response_model=CurrentUser,
    responses={
        401: {"model": ErrorEnvelope, "description": "ID token invalid or expired"},
        403: {"model": ErrorEnvelope, "description": "E-mail not verified, or not invited"},
    },
)
async def start_session(
    body: SessionRequest,
    request: Request,
    response: Response,
    service: Service,
    settings: SettingsDep,
) -> CurrentUser | JSONResponse:
    """Exchange a Firebase ID token for an app session (HttpOnly cookie)."""
    result = await service.start_session(body.id_token, request_meta(request))
    # Failures are returned (not raised) so their audit entries are committed.
    if result.failure is not None or result.token is None or result.actor is None:
        code, error_code, message = FAILURES[result.failure or "invalid_token"]
        return error_response(code, error_code, message)
    set_session_cookie(response, result.token, settings)
    set_csrf_cookie(response, settings)  # rotate CSRF with the session
    return CurrentUser.from_actor(result.actor)


@router.post(
    "/register",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=Message,
    responses={
        401: {"model": ErrorEnvelope, "description": "ID token invalid"},
        409: {"model": ErrorEnvelope, "description": "E-mail already has an account"},
    },
)
async def register(body: RegisterRequest, request: Request, service: Service) -> Message:
    """Self sign-up. The account stays PENDING (no access) until an approver acts."""
    await service.register(body.id_token, body.full_name.strip(), request_meta(request))
    return Message(message=REGISTERED)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def logout(
    request: Request,
    response: Response,
    actor: CurrentActor,
    service: Service,
    settings: SettingsDep,
) -> None:
    token = request.cookies.get(settings.session_cookie_name, "")
    await service.sign_out(token, actor, request_meta(request))
    clear_session_cookie(response, settings)


@router.get(
    "/me",
    response_model=CurrentUser,
    responses={401: {"model": ErrorEnvelope, "description": "Not signed in"}},
)
async def current_user(actor: CurrentActor) -> CurrentUser:
    return CurrentUser.from_actor(actor)


@router.post("/sessions/revoke-others", response_model=Message)
async def revoke_other_sessions(
    request: Request,
    actor: CurrentActor,
    service: Service,
    settings: SettingsDep,
) -> Message:
    """Sign out every other session of the current user (after a password change)."""
    token = request.cookies.get(settings.session_cookie_name, "")
    await service.revoke_other_sessions(actor, token, request_meta(request))
    return Message(message="Your other sessions have been signed out.")
