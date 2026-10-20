"""Firebase identity → app session, through HTTP, with a fake identity provider.

The real Firebase Admin SDK is exercised against the Auth Emulator in
test_firebase_emulator.py.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.permissions import DEFAULT_ROLES
from app.core.clock import FixedClock, get_clock
from app.core.errors import Conflict
from app.db.session import get_session
from app.main import create_app
from app.modules.auth.service import AuthService
from app.platform.audit.models import AuditLog
from app.platform.identity.firebase import (
    IdentityClaims,
    InvalidIdentityTokenError,
    get_identity_provider,
)
from app.platform.identity.models import Role, User, UserRole, UserSession
from tests.conftest import make_settings

pytestmark = pytest.mark.integration


class FakeIdentity:
    """Tokens are "token-<uid>" padded with dots to a realistic length."""

    def __init__(self) -> None:
        self.accounts: dict[str, IdentityClaims] = {}
        self.created: list[str] = []

    def account(self, uid: str, email: str, *, verified: bool = True) -> str:
        self.accounts[uid] = IdentityClaims(uid=uid, email=email, email_verified=verified)
        return f"token-{uid}".ljust(40, ".")

    async def verify_id_token(self, id_token: str) -> IdentityClaims:
        uid = id_token.removeprefix("token-").rstrip(".")
        if uid not in self.accounts:
            raise InvalidIdentityTokenError("unknown token")
        return self.accounts[uid]

    async def ensure_user(self, email: str, display_name: str) -> str:
        uid = f"uid-{len(self.created) + 1}"
        self.created.append(email)
        self.accounts[uid] = IdentityClaims(uid=uid, email=email, email_verified=False)
        return uid

    async def password_setup_link(self, email: str, continue_url: str) -> str:
        return f"https://auth.example/reset?email={email}&continue={continue_url}"

    async def email_verified(self, uid: str) -> bool | None:
        claims = self.accounts.get(uid)
        return claims.email_verified if claims else None

    async def delete_user(self, uid: str) -> None:
        self.accounts.pop(uid, None)

    def verify(self, uid: str) -> str:
        """The user clicked the verification link: same account, verified e-mail."""
        claims = self.accounts[uid]
        self.accounts[uid] = IdentityClaims(uid=uid, email=claims.email, email_verified=True)
        return f"token-{uid}".ljust(40, ".")


@pytest.fixture
async def roles(db_session: AsyncSession) -> dict[str, Role]:
    created = {}
    # Migrations may already have created some roles (e.g. org_admin in 0010).
    existing = {r.key: r for r in (await db_session.execute(select(Role))).scalars()}
    for definition in DEFAULT_ROLES:
        role = existing.get(definition.key) or Role(key=definition.key, name=definition.name)
        role.permissions = sorted(definition.permissions)
        db_session.add(role)
        created[definition.key] = role
    await db_session.flush()
    return created


async def invited_user(
    session: AsyncSession,
    role: Role,
    *,
    email: str = "ada@example.com",
    uid: str | None = None,
    active: bool = True,
) -> User:
    user = User(
        email=email,
        full_name="Ada Lovelace",
        firebase_uid=uid,
        is_active=active,
        approved_at=datetime.now(UTC),
    )
    session.add(user)
    await session.flush()
    session.add(UserRole(user_id=user.id, role_id=role.id))
    await session.flush()
    return user


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(datetime.now(UTC))


@pytest.fixture
def identity() -> FakeIdentity:
    return FakeIdentity()


@pytest.fixture
async def client(
    db_session: AsyncSession,
    migrated_database_url: str,
    clock: FixedClock,
    identity: FakeIdentity,
) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(make_settings(database_url=migrated_database_url))

    async def session_override() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[get_clock] = lambda: clock
    app.dependency_overrides[get_identity_provider] = lambda: identity
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as http:

        async def add_csrf(request: httpx.Request) -> None:
            # Like lib/api-client.ts: echo the CSRF cookie on every write.
            token = http.cookies.get("delphin_csrf")
            if token and "X-CSRF-Token" not in request.headers:
                request.headers["X-CSRF-Token"] = token

        http.event_hooks["request"] = [add_csrf]
        yield http


async def start(http: httpx.AsyncClient, id_token: str) -> httpx.Response:
    return await http.post("/api/v1/auth/session", json={"id_token": id_token})


async def test_first_sign_in_links_the_invited_user(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    roles: dict[str, Role],
    identity: FakeIdentity,
) -> None:
    user = await invited_user(db_session, roles["account_manager"])
    token = identity.account("fb-ada", "ADA@example.com")  # e-mail match is case-insensitive

    response = await start(client, token)
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "ada@example.com"
    assert body["roles"] == ["account_manager"]
    assert "clients.create" in body["permissions"]
    cookies = response.headers.get_list("set-cookie")
    assert any(c.startswith("delphin_session=") and "HttpOnly" in c for c in cookies)
    assert any(c.startswith("delphin_csrf=") for c in cookies)
    assert user.firebase_uid == "fb-ada"
    assert user.activated_at is not None

    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["id"] == str(user.id)

    raw = client.cookies["delphin_session"]
    stored = (await db_session.execute(select(UserSession.token_hash))).scalars().all()
    assert raw not in stored  # stored hashed only

    forged = await client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": "forged"})
    assert forged.status_code == 403
    assert (await client.post("/api/v1/auth/logout")).status_code == 204
    assert (await client.get("/api/v1/auth/me")).status_code == 401

    actions = (await db_session.execute(select(AuditLog.action))).scalars().all()
    assert {"auth.login", "auth.logout"} <= set(actions)


async def test_unverified_email_is_refused(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    roles: dict[str, Role],
    identity: FakeIdentity,
) -> None:
    await invited_user(db_session, roles["employee"])
    response = await start(client, identity.account("fb-ada", "ada@example.com", verified=False))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "email_not_verified"
    assert "delphin_session" not in client.cookies


async def test_only_invited_active_users_get_in(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    roles: dict[str, Role],
    identity: FakeIdentity,
) -> None:
    stranger = await start(client, identity.account("fb-x", "stranger@example.com"))
    assert stranger.status_code == 403
    assert stranger.json()["error"]["code"] == "no_access"

    await invited_user(db_session, roles["employee"], email="off@example.com", active=False)
    inactive = await start(client, identity.account("fb-off", "off@example.com"))
    assert inactive.status_code == 403

    bad = await start(client, "not-a-real-token".ljust(40, "z"))
    assert bad.status_code == 401
    assert bad.json()["error"]["code"] == "unauthorized"

    reasons = (await db_session.execute(select(AuditLog.context))).scalars().all()
    assert {r.get("reason") for r in reasons} >= {"no_access", "invalid_token"}


async def test_linked_user_is_not_taken_over_by_another_firebase_account(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    roles: dict[str, Role],
    identity: FakeIdentity,
) -> None:
    await invited_user(db_session, roles["employee"], uid="fb-original")
    # Someone else now holds the same e-mail in Firebase under a different uid.
    imposter = await start(client, identity.account("fb-imposter", "ada@example.com"))
    assert imposter.status_code == 403
    original = await start(client, identity.account("fb-original", "ada@example.com"))
    assert original.status_code == 200


async def test_sessions_expire_and_follow_deactivation(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    roles: dict[str, Role],
    identity: FakeIdentity,
    clock: FixedClock,
) -> None:
    user = await invited_user(db_session, roles["employee"])
    assert (await start(client, identity.account("fb-ada", user.email))).status_code == 200
    clock.advance(timedelta(hours=13))  # default TTL is 12 h
    assert (await client.get("/api/v1/auth/me")).status_code == 401

    clock.advance(timedelta(hours=-13))
    user.is_active = False
    await db_session.flush()
    assert (await client.get("/api/v1/auth/me")).status_code == 401


async def test_revoke_other_sessions_keeps_this_one(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    roles: dict[str, Role],
    identity: FakeIdentity,
) -> None:
    user = await invited_user(db_session, roles["employee"])
    token = identity.account("fb-ada", user.email)
    assert (await start(client, token)).status_code == 200  # an "other device"
    assert (await start(client, token)).status_code == 200  # this browser (latest cookie)
    response = await client.post("/api/v1/auth/sessions/revoke-others")
    assert response.status_code == 200
    assert (await client.get("/api/v1/auth/me")).status_code == 200
    live = await db_session.execute(
        select(func.count()).select_from(UserSession).where(UserSession.revoked_at.is_(None))
    )
    assert live.scalar_one() == 1


async def test_invitation_creates_both_accounts_and_a_setup_link(
    db_session: AsyncSession, roles: dict[str, Role], identity: FakeIdentity, clock: FixedClock
) -> None:
    service = AuthService(db_session, clock=clock, settings=make_settings(), identity=identity)
    invitation = await service.invite(
        email="new@example.com", full_name="New Person", role_key="super_admin"
    )
    assert identity.created == ["new@example.com"]
    assert invitation.user.firebase_uid == "uid-1"
    assert invitation.link.startswith("https://auth.example/reset?email=new@example.com")
    assert invitation.link.endswith("/login")

    with pytest.raises(Conflict, match="already exists"):
        await service.invite(email="NEW@example.com", full_name="Dup", role_key="employee")


# ---------------------------------------------------------------- self sign-up


async def register(
    http: httpx.AsyncClient, id_token: str, name: str = "Sam Signup"
) -> httpx.Response:
    return await http.post("/api/v1/auth/register", json={"id_token": id_token, "full_name": name})


async def sign_in_as_admin(
    http: httpx.AsyncClient, session: AsyncSession, roles: dict[str, Role], identity: FakeIdentity
) -> None:
    admin = await invited_user(session, roles["super_admin"], email="boss@example.com")
    response = await start(http, identity.account("fb-boss", admin.email))
    assert response.status_code == 200


async def test_sign_up_waits_for_approval_then_gets_the_chosen_role(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    roles: dict[str, Role],
    identity: FakeIdentity,
) -> None:
    token = identity.account("fb-sam", "sam@example.com", verified=False)
    response = await register(client, token)
    assert response.status_code == 202
    assert "approve" in response.json()["message"]
    assert (await register(client, token)).status_code == 202  # retry is harmless

    pending = (
        await db_session.execute(select(User).where(User.email == "sam@example.com"))
    ).scalar_one()
    assert pending.approved_at is None
    assert pending.firebase_uid == "fb-sam"

    # Unverified first, then verified-but-pending: no session either way.
    assert (await start(client, token)).json()["error"]["code"] == "email_not_verified"
    waiting = await start(client, identity.verify("fb-sam"))
    assert waiting.status_code == 403
    assert waiting.json()["error"]["code"] == "pending_approval"
    assert "delphin_session" not in client.cookies

    await sign_in_as_admin(client, db_session, roles, identity)
    listed = await client.get("/api/v1/team/registrations")
    assert listed.status_code == 200
    assert [(r["email"], r["email_verified"]) for r in listed.json()] == [("sam@example.com", True)]
    unknown_role = await client.post(
        f"/api/v1/team/registrations/{pending.id}/approve", json={"role": "wizard"}
    )
    assert unknown_role.status_code == 422
    approved = await client.post(
        f"/api/v1/team/registrations/{pending.id}/approve", json={"role": "account_manager"}
    )
    assert approved.status_code == 204
    again = await client.post(
        f"/api/v1/team/registrations/{pending.id}/approve", json={"role": "finance"}
    )
    assert again.status_code == 404  # already handled
    assert (await client.get("/api/v1/team/registrations")).json() == []

    await client.post("/api/v1/auth/logout")
    sam = await start(client, identity.verify("fb-sam"))
    assert sam.status_code == 200
    assert sam.json()["roles"] == ["account_manager"]
    assert pending.approved_by_id is not None


async def test_rejecting_deletes_both_accounts(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    roles: dict[str, Role],
    identity: FakeIdentity,
) -> None:
    await register(client, identity.account("fb-spam", "spam@example.com"))
    pending = (
        await db_session.execute(select(User).where(User.email == "spam@example.com"))
    ).scalar_one()
    await sign_in_as_admin(client, db_session, roles, identity)
    response = await client.post(f"/api/v1/team/registrations/{pending.id}/reject")
    assert response.status_code == 204
    assert "fb-spam" not in identity.accounts
    gone = await db_session.execute(select(User).where(User.email == "spam@example.com"))
    assert gone.scalar_one_or_none() is None
    actions = (await db_session.execute(select(AuditLog.action))).scalars().all()
    assert {"auth.registered", "team.registration_rejected"} <= set(actions)


async def test_sign_up_cannot_claim_an_existing_email(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    roles: dict[str, Role],
    identity: FakeIdentity,
) -> None:
    await invited_user(db_session, roles["employee"], uid="fb-real")
    response = await register(client, identity.account("fb-other", "ada@example.com"))
    assert response.status_code == 409
    assert (await register(client, "garbage-token".ljust(40, "z"))).status_code == 401


async def test_only_approvers_see_or_decide_sign_ups(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    roles: dict[str, Role],
    identity: FakeIdentity,
) -> None:
    assert (await client.get("/api/v1/team/registrations")).status_code == 401
    user = await invited_user(db_session, roles["account_manager"])
    assert (await start(client, identity.account("fb-ada", user.email))).status_code == 200
    assert (await client.get("/api/v1/team/registrations")).status_code == 403
