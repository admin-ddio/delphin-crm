"""Clients API end to end on PostgreSQL: create, duplicates, scope, edit, audit."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.actor import Actor
from app.authz.dependencies import get_actor
from app.authz.permissions import DEFAULT_ROLES
from app.db.session import get_session
from app.main import create_app
from app.platform.audit.models import AuditLog
from app.platform.identity.models import Role, User, UserRole
from app.platform.identity.sessions import actor_for_user
from tests.conftest import make_settings

pytestmark = pytest.mark.integration


@dataclass
class World:
    http: httpx.AsyncClient
    session: AsyncSession
    roles: dict[str, Role]
    current: list[Actor] = field(default_factory=list)

    async def user(self, email: str, role: str, name: str | None = None) -> User:
        user = User(
            email=email,
            full_name=name or email.partition("@")[0].title(),
            is_active=True,
            approved_at=datetime.now(UTC),
        )
        self.session.add(user)
        await self.session.flush()
        self.session.add(UserRole(user_id=user.id, role_id=self.roles[role].id))
        await self.session.flush()
        return user

    async def act_as(self, user: User) -> None:
        self.current[:] = [await actor_for_user(self.session, user)]

    async def create(self, manager: User, **fields: object) -> httpx.Response:
        body = {"name": "Acme Ltd", "account_manager_id": str(manager.id), **fields}
        return await self.http.post("/api/v1/clients", json=body)


@pytest.fixture
async def world(db_session: AsyncSession, migrated_database_url: str) -> AsyncIterator[World]:
    roles = {}
    for definition in DEFAULT_ROLES:
        role = Role(
            key=definition.key, name=definition.name, permissions=sorted(definition.permissions)
        )
        db_session.add(role)
        roles[definition.key] = role
    await db_session.flush()

    app = create_app(make_settings(database_url=migrated_database_url))
    current: list[Actor] = []

    async def session_override() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[get_actor] = lambda: current[0]
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as http:
        yield World(http=http, session=db_session, roles=roles, current=current)


async def test_create_assigns_codes_normalises_and_audits(world: World) -> None:
    am = await world.user("anika@example.com", "account_manager", "Anika Shah")
    await world.act_as(am)

    first = await world.create(
        am,
        website="https://www.Acme.com/about",
        industry="Manufacturing",
        contact_name="Pat Buyer",
        contact_email="pat@acme.com",
    )
    assert first.status_code == 201, first.text
    body = first.json()
    assert body["code"] == "CL-0001"
    assert body["domain"] == "acme.com"
    assert body["status"] == "contract_pending"
    assert body["status_label"] == "Contract pending"
    assert body["account_manager"]["full_name"] == "Anika Shah"
    assert body["can_edit"] is True

    second = await world.create(am, name="Globex", website="globex.io")
    assert second.json()["code"] == "CL-0002"

    audit = (
        (await world.session.execute(select(AuditLog).where(AuditLog.action == "client.created")))
        .scalars()
        .all()
    )
    assert len(audit) == 2
    assert audit[0].changes["name"] == "Acme Ltd"

    activity = await world.http.get(f"/api/v1/clients/{body['id']}/activity")
    assert [a["summary"] for a in activity.json()] == ["Client Acme Ltd created"]
    assert activity.json()[0]["actor"]["full_name"] == "Anika Shah"


async def test_duplicate_domain_is_a_hard_block(world: World) -> None:
    am = await world.user("am@example.com", "account_manager")
    await world.act_as(am)
    assert (await world.create(am, website="acme.com")).status_code == 201

    for variant in ("https://www.acme.com", "ACME.com/contact", "http://acme.com"):
        response = await world.create(
            am, name="Totally Different", website=variant, confirm_different_business=True
        )
        assert response.status_code == 409, variant
        error = response.json()["error"]
        assert error["details"]["reason"] == "duplicate_domain"
        assert "acme.com already exists (Acme Ltd)" in error["message"]


async def test_similar_name_warns_until_confirmed(world: World) -> None:
    am = await world.user("am@example.com", "account_manager")
    await world.act_as(am)
    assert (await world.create(am, name="The Acme Company")).status_code == 201

    warned = await world.create(am, name="ACME, Inc.")
    assert warned.status_code == 409
    assert warned.json()["error"]["details"]["reason"] == "similar_name"
    assert "different business" in warned.json()["error"]["message"]

    confirmed = await world.create(am, name="ACME, Inc.", confirm_different_business=True)
    assert confirmed.status_code == 201


async def test_list_search_filter_sort_and_paginate(world: World) -> None:
    am = await world.user("am@example.com", "account_manager")
    await world.act_as(am)
    for name, site in [("Zeta Ltd", "zeta.io"), ("Alpha Ltd", "alpha.io"), ("Mid Co", "mid.io")]:
        assert (await world.create(am, name=name, website=site)).status_code == 201

    page = (await world.http.get("/api/v1/clients?page_size=2")).json()
    assert page["total"] == 3
    assert [c["name"] for c in page["items"]] == ["Alpha Ltd", "Mid Co"]

    desc = (await world.http.get("/api/v1/clients?sort=-name")).json()
    assert desc["items"][0]["name"] == "Zeta Ltd"

    found = (await world.http.get("/api/v1/clients?q=zeta")).json()
    assert [c["name"] for c in found["items"]] == ["Zeta Ltd"]
    by_code = (await world.http.get("/api/v1/clients?q=CL-0002")).json()
    assert [c["name"] for c in by_code["items"]] == ["Alpha Ltd"]

    filtered = (await world.http.get("/api/v1/clients?status=active")).json()
    assert filtered["total"] == 0
    bad_sort = await world.http.get("/api/v1/clients?sort=password")
    assert bad_sort.status_code == 422


async def test_scope_who_sees_what(world: World) -> None:
    am = await world.user("am@example.com", "account_manager")
    await world.act_as(am)
    client_id = (await world.create(am)).json()["id"]

    for role in ("project_manager", "finance", "super_admin"):
        await world.act_as(await world.user(f"{role}@example.com", role))
        assert (await world.http.get("/api/v1/clients")).json()["total"] == 1, role
        assert (await world.http.get(f"/api/v1/clients/{client_id}")).status_code == 200

    await world.act_as(await world.user("emp@example.com", "employee"))
    assert (await world.http.get("/api/v1/clients")).json()["total"] == 0
    hidden = await world.http.get(f"/api/v1/clients/{client_id}")
    assert hidden.status_code == 404  # not "forbidden": existence isn't revealed
    assert (await world.http.get(f"/api/v1/clients/{client_id}/activity")).status_code == 404


async def test_only_the_clients_own_account_manager_edits(world: World) -> None:
    owner = await world.user("owner@example.com", "account_manager", "Owner Am")
    other = await world.user("other@example.com", "account_manager", "Other Am")
    await world.act_as(owner)
    client_id = (await world.create(owner, website="acme.com")).json()["id"]
    await world.create(owner, name="Globex", website="globex.io")

    await world.act_as(other)
    detail = (await world.http.get(f"/api/v1/clients/{client_id}")).json()
    assert detail["can_edit"] is False
    denied = await world.http.patch(f"/api/v1/clients/{client_id}", json={"industry": "Retail"})
    assert denied.status_code == 403

    await world.act_as(await world.user("pm@example.com", "project_manager"))
    assert (
        await world.http.patch(f"/api/v1/clients/{client_id}", json={"industry": "Retail"})
    ).status_code == 403

    await world.act_as(owner)
    clash = await world.http.patch(f"/api/v1/clients/{client_id}", json={"website": "globex.io"})
    assert clash.status_code == 409
    similar = await world.http.patch(f"/api/v1/clients/{client_id}", json={"name": "Globex Inc"})
    assert similar.json()["error"]["details"]["reason"] == "similar_name"

    updated = await world.http.patch(
        f"/api/v1/clients/{client_id}",
        json={"industry": "Retail", "website": "acme.co.uk", "account_manager_id": str(other.id)},
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["industry"] == "Retail"
    assert body["domain"] == "acme.co.uk"
    assert body["account_manager"]["full_name"] == "Other Am"
    assert body["can_edit"] is False  # handed over to the other AM

    audit = (
        await world.session.execute(select(AuditLog).where(AuditLog.action == "client.updated"))
    ).scalar_one()
    assert audit.changes["industry"] == [None, "Retail"]
    assert audit.changes["website"] == ["acme.com", "acme.co.uk"]


async def test_create_rules(world: World) -> None:
    am = await world.user("am@example.com", "account_manager")
    employee = await world.user("emp@example.com", "employee")
    boss = await world.user("boss@example.com", "super_admin", "Big Boss")

    await world.act_as(await world.user("pm@example.com", "project_manager"))
    assert (await world.create(am)).status_code == 403  # PMs can't create clients

    await world.act_as(am)
    not_am = await world.create(employee)
    assert not_am.status_code == 422
    assert "Account Manager" in not_am.json()["error"]["message"]
    blank = await world.http.post(
        "/api/v1/clients", json={"name": "   ", "account_manager_id": str(am.id)}
    )
    assert blank.status_code == 422
    bad_email = await world.create(am, contact_email="nope")
    assert bad_email.status_code == 422

    options = (await world.http.get("/api/v1/clients/account-managers")).json()
    assert {o["full_name"] for o in options} == {"Am", "Big Boss"}
    assert str(boss.id) in {o["id"] for o in options}
