"""Onboarding API end to end on PostgreSQL: the full workflow and every gate."""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.actor import Actor
from app.authz.dependencies import get_actor
from app.authz.permissions import DEFAULT_ROLES
from app.db.session import get_session
from app.main import create_app
from app.modules.clients.models import Client
from app.platform.audit.models import AuditLog
from app.platform.identity.models import Role, User, UserRole
from app.platform.identity.sessions import actor_for_user
from tests.conftest import make_settings

pytestmark = pytest.mark.integration

ANSWERS = {
    "business_goals": "Grow qualified organic leads",
    "products_services": "Industrial widgets",
    "target_markets": "US and Canada",
    "target_audiences": "Procurement managers",
    "competitors": "WidgetCo",
    "brand_voice": "Practical and expert",
}


@dataclass
class World:
    http: httpx.AsyncClient
    session: AsyncSession
    roles: dict[str, Role]
    current: list[Actor] = field(default_factory=list)

    async def user(self, email: str, role: str) -> User:
        user = User(
            email=email,
            full_name=email.partition("@")[0].title(),
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

    async def client(self, manager: User, **fields: Any) -> str:
        body = {
            "name": "Acme Ltd",
            "website": "acme.com",
            "industry": "Retail",
            "contact_name": "Pat Buyer",
            "contact_email": "pat@acme.com",
            "account_manager_id": str(manager.id),
            **fields,
        }
        response = await self.http.post("/api/v1/clients", json=body)
        assert response.status_code == 201, response.text
        return str(response.json()["id"])

    async def post(self, client_id: str, path: str, body: Any = None) -> httpx.Response:
        return await self.http.post(f"/api/v1/onboarding/clients/{client_id}/{path}", json=body)

    async def detail(self, client_id: str) -> dict[str, Any]:
        response = await self.http.get(f"/api/v1/onboarding/clients/{client_id}")
        assert response.status_code == 200, response.text
        return dict(response.json())


def step(detail: dict[str, Any], key: str) -> str:
    return str(next(s["state"] for s in detail["steps"] if s["key"] == key))


def error(response: httpx.Response) -> str:
    return str(response.json()["error"]["message"])


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


async def test_full_workflow_to_active(world: World) -> None:
    am = await world.user("anika@example.com", "account_manager")
    pm = await world.user("tomas@example.com", "project_manager")
    specialist = await world.user("jordan@example.com", "employee")
    await world.act_as(am)
    cid = await world.client(am)

    fresh = await world.detail(cid)
    assert fresh["status"] == "in_progress"
    assert fresh["progress"] == 15  # created + profile
    assert [a["key"] for a in fresh["access"]] == ["GSC", "GA4", "CMS", "AHREFS", "GDRIVE"]
    assert fresh["permissions"] == {"manage": True, "verify_access": True, "confirm_kpis": True}

    # 1. Contract: record, then sign → client status Onboarding.
    assert "Record the contract" in error(await world.post(cid, "contract", {"action": "sign"}))
    assert (await world.post(cid, "contract", {"action": "record"})).status_code == 200
    signed = (await world.post(cid, "contract", {"action": "sign"})).json()
    assert step(signed, "contract") == "done"
    client = await world.session.get(Client, signed["client_id"])
    assert client is not None
    assert client.status == "onboarding"

    # 4–5. Questionnaire via the public single-use link.
    link = (await world.post(cid, "questionnaire/send")).json()
    token = re.search(r"/q/(\S+)$", link["url"])
    assert token
    public = await world.http.get(f"/api/v1/onboarding/questionnaire/{token.group(1)}")
    assert public.status_code == 200
    assert public.json()["client_name"] == "Acme Ltd"
    assert len(public.json()["questions"]) == 6
    partial = await world.http.post(
        f"/api/v1/onboarding/questionnaire/{token.group(1)}",
        json={"answers": {"business_goals": "x"}},
    )
    assert partial.status_code == 422
    submitted = await world.http.post(
        f"/api/v1/onboarding/questionnaire/{token.group(1)}", json={"answers": ANSWERS}
    )
    assert submitted.status_code == 204
    reused = await world.http.get(f"/api/v1/onboarding/questionnaire/{token.group(1)}")
    assert reused.status_code == 404  # single use
    after_q = await world.detail(cid)
    assert step(after_q, "q_done") == "done"
    assert after_q["questions"][0]["answer"] == "Grow qualified organic leads"

    # 6–7. Access: verify needs "received"; a PM verifies.
    early = await world.http.patch(
        f"/api/v1/onboarding/clients/{cid}/access/GSC", json={"status": "verified"}
    )
    assert "received before it can be verified" in error(early)
    assert (await world.post(cid, "access/receive-all")).status_code == 200
    await world.act_as(pm)
    for key in ("GSC", "GA4", "CMS", "AHREFS", "GDRIVE"):
        verified = await world.http.patch(
            f"/api/v1/onboarding/clients/{cid}/access/{key}", json={"status": "verified"}
        )
        assert verified.status_code == 200, verified.text
    assert verified.json()["access"][0]["verified_by"]["full_name"] == "Tomas"
    assert step(verified.json(), "access_ok") == "done"
    # A PM may verify but not run the workflow.
    assert (
        await world.post(cid, "kpis", {"metric": "x", "baseline": 1, "target": 2, "unit": "u"})
    ).status_code == 403
    await world.act_as(am)

    # 8. KPIs need the client's confirmation.
    kpi = {
        "metric": "Organic sessions",
        "baseline": "1200",
        "target": "3000",
        "unit": "sessions / month",
    }
    assert (await world.post(cid, "kpis", kpi)).status_code == 200
    confirmed = (
        await world.post(cid, "kpis/confirm", {"confirmed_by": "Pat Buyer", "via": "email"})
    ).json()
    assert confirmed["kpis"][0]["confirmed_by_name"] == "Pat Buyer"
    assert step(confirmed, "kpi") == "done"

    # 9–10. Kickoffs and team.
    assert "Schedule the client kickoff" in error(
        await world.post(cid, "kickoffs/client", {"action": "complete"})
    )
    await world.post(cid, "kickoffs/client", {"action": "schedule", "at": "2026-11-02T10:00:00Z"})
    await world.post(cid, "kickoffs/client", {"action": "complete", "notes": "Goals agreed"})
    options = (await world.http.get(f"/api/v1/onboarding/clients/{cid}/team/options")).json()
    assert {o["full_name"] for o in options} == {"Tomas", "Jordan"}
    team = await world.post(cid, "team", {"user_id": str(specialist.id)})
    assert team.json()["team"][0]["full_name"] == "Jordan"
    assert (await world.post(cid, "team", {"user_id": str(specialist.id)})).status_code == 409
    await world.post(cid, "kickoffs/internal", {"action": "schedule"})

    # 11. Review is gated on steps 1–10.
    blocked = await world.post(cid, "review")
    assert blocked.status_code == 422
    assert "Internal team kickoff" in error(blocked)
    await world.post(cid, "kickoffs/internal", {"action": "complete", "notes": "Roles assigned"})
    assert step((await world.post(cid, "review")).json(), "review") == "done"

    # 12. Completion → client Active, workflow locked.
    done = (await world.post(cid, "complete")).json()
    assert done["status"] == "completed"
    assert done["progress"] == 92
    assert done["permissions"]["manage"] is False
    await world.session.refresh(client)
    assert client.status == "active"
    assert "already completed" in error(await world.post(cid, "contract", {"action": "record"}))

    # The specialist on the team now sees the client (but can't run onboarding).
    await world.act_as(specialist)
    assert (await world.http.get(f"/api/v1/clients/{cid}")).status_code == 200
    assert (await world.detail(cid))["permissions"]["manage"] is False

    # Everything is on the timeline and in the audit log.
    activity = (await world.http.get(f"/api/v1/clients/{cid}/activity")).json()
    summaries = [a["summary"] for a in activity]
    assert "Onboarding completed — the client is now Active" in summaries
    assert "Client submitted the onboarding questionnaire" in summaries
    assert "Pat Buyer confirmed the KPI targets via e-mail" in summaries
    actions = set((await world.session.execute(select(AuditLog.action))).scalars().all())
    assert {"onboarding.contract_sign", "onboarding.completed", "onboarding.reviewed"} <= actions


async def test_completion_gates_and_blocking(world: World) -> None:
    am = await world.user("am@example.com", "account_manager")
    await world.act_as(am)
    cid = await world.client(am)

    assert "access items must be verified" in error(await world.post(cid, "complete"))

    await world.post(cid, "access/receive-all")
    rejected = await world.http.patch(
        f"/api/v1/onboarding/clients/{cid}/access/GA4", json={"status": "rejected"}
    )
    body = rejected.json()
    assert body["status"] == "blocked"
    assert step(body, "access_in") == "blocked"
    # Re-receiving clears the block.
    again = await world.http.patch(
        f"/api/v1/onboarding/clients/{cid}/access/GA4", json={"status": "received"}
    )
    assert again.json()["status"] == "in_progress"
    for key in ("GSC", "GA4", "CMS", "AHREFS", "GDRIVE"):
        await world.http.patch(
            f"/api/v1/onboarding/clients/{cid}/access/{key}", json={"status": "verified"}
        )
    assert "KPI targets require client confirmation" in error(await world.post(cid, "complete"))

    await world.post(cid, "kpis", {"metric": "Leads", "baseline": 1, "target": 5, "unit": "leads"})
    await world.post(cid, "kpis/confirm", {"confirmed_by": "Pat", "via": "call"})
    incomplete = await world.post(cid, "complete")
    assert "Can't complete onboarding. Incomplete:" in error(incomplete)
    assert "Contract signed" in incomplete.json()["error"]["details"]["incomplete"]

    # Confirmed KPIs can't be removed.
    kpi_id = (await world.detail(cid))["kpis"][0]["id"]
    removed = await world.http.delete(f"/api/v1/onboarding/clients/{cid}/kpis/{kpi_id}")
    assert "confirmed can't be removed" in error(removed)


async def test_only_the_clients_account_manager_runs_onboarding(world: World) -> None:
    owner = await world.user("owner@example.com", "account_manager")
    other = await world.user("other@example.com", "account_manager")
    employee = await world.user("emp@example.com", "employee")
    finance = await world.user("fin@example.com", "finance")
    await world.act_as(owner)
    cid = await world.client(owner)

    await world.act_as(other)
    assert (await world.detail(cid))["permissions"]["manage"] is False
    denied = await world.post(cid, "contract", {"action": "record"})
    assert denied.status_code == 403
    assert "Account Manager" in error(denied)

    await world.act_as(finance)  # sees the client, can't verify access
    await world.act_as(owner)
    await world.post(cid, "access/receive-all")
    await world.act_as(finance)
    assert (
        await world.http.patch(
            f"/api/v1/onboarding/clients/{cid}/access/GSC", json={"status": "verified"}
        )
    ).status_code == 403

    await world.act_as(employee)  # not on the team: the client doesn't exist for them
    assert (await world.http.get(f"/api/v1/onboarding/clients/{cid}")).status_code == 404


async def test_board_lists_progress_and_manual_answers(world: World) -> None:
    am = await world.user("am@example.com", "account_manager")
    await world.act_as(am)
    first = await world.client(am, name="Beta Co", website="beta.io")
    await world.client(am, name="Alpha Co", website="alpha.io", industry=None)

    await world.post(first, "questionnaire/send")
    missing = await world.post(first, "questionnaire/answers", {"answers": {"brand_voice": "Calm"}})
    assert missing.status_code == 422
    assert "Please answer every question" in error(missing)
    recorded = await world.post(first, "questionnaire/answers", {"answers": ANSWERS})
    assert step(recorded.json(), "q_done") == "done"

    board = (await world.http.get("/api/v1/onboarding")).json()
    assert [row["client_name"] for row in board] == ["Alpha Co", "Beta Co"]
    alpha = board[0]
    assert alpha["current_step"] == "Contract signed"
    assert alpha["progress"] == 8  # profile incomplete (no industry)
    assert board[1]["progress"] == 31  # created, profile, q sent, q done
