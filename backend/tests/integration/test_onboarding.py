"""Onboarding API end to end on PostgreSQL: the full workflow and every gate."""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.actor import Actor
from app.authz.dependencies import get_actor
from app.authz.permissions import DEFAULT_ROLES
from app.core.clock import FixedClock
from app.db.session import get_session
from app.main import create_app
from app.modules.clients.models import Client
from app.modules.onboarding.service import OnboardingService
from app.platform.audit.models import AuditLog
from app.platform.identity.models import Role, User, UserRole
from app.platform.identity.sessions import actor_for_user
from app.platform.notifications.models import Notification
from app.platform.storage.local import LocalStorage, get_storage
from tests.conftest import make_settings

pytestmark = pytest.mark.integration

ANSWERS: dict[str, Any] = {
    "business_goals": {
        "goals": ["organic_traffic", "leads"],
        "details": "Increase organic traffic by 40% in 12 months",
    },
    "target_markets": {"locations": "India, UAE", "audiences": "Procurement managers"},
    "competitors": {"competitors": [{"name": "WidgetCo", "website": "widgetco.com"}]},
    "brand_voice": {"tones": ["professional", "friendly"]},
    "past_seo": {"worked_before": "yes", "details": "Agency until 2025"},
    "additional": {"products_services": "Industrial widgets"},
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
            "contact_designation": "Marketing Head",
            "contact_email": "pat@acme.com",
            "contact_phone": "+91 98765 43210",
            "contract_start": "2026-05-01",
            "contract_end": "2027-04-30",
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
async def world(
    db_session: AsyncSession, migrated_database_url: str, tmp_path: Path
) -> AsyncIterator[World]:
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
    app.dependency_overrides[get_storage] = lambda: LocalStorage(tmp_path)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as http:
        yield World(http=http, session=db_session, roles=roles, current=current)


def stage(detail: dict[str, Any], key: str) -> str:
    return str(next(s["state"] for s in detail["stages"] if s["key"] == key))


async def notifications(w: World, user: User) -> list[str]:
    rows = (
        await w.session.execute(select(Notification.title).where(Notification.user_id == user.id))
    ).scalars()
    return list(rows)


async def meeting(w: World, client_id: str, kind: str, **extra: Any) -> dict[str, Any]:
    start = datetime.now(UTC) - timedelta(hours=2)
    response = await w.http.post(
        "/api/v1/meetings",
        json={
            "client_id": client_id,
            "title": "Kickoff Call" if kind == "kickoff" else "Internal Kickoff",
            "type": kind,
            "starts_at": start.isoformat(),
            "ends_at": (start + timedelta(hours=1)).isoformat(),
            "platform": "google_meet",
            **extra,
        },
    )
    assert response.status_code == 201, response.text
    return dict(response.json())


async def test_full_workflow_to_active(world: World) -> None:  # the whole journey
    am = await world.user("anika@example.com", "account_manager")
    pm = await world.user("tomas@example.com", "project_manager")
    specialist = await world.user("jordan@example.com", "employee")
    await world.act_as(am)
    cid = await world.client(am)

    fresh = await world.detail(cid)
    assert fresh["client"]["status"] == "onboarding"
    assert fresh["progress"] == 23  # contract (captured at creation), created, profile
    assert [step(fresh, k) for k in ("contract", "created", "profile")] == ["done"] * 3
    assert stage(fresh, "client") == "completed"
    assert stage(fresh, "questionnaire") == "pending"
    assert fresh["next_actions"][0]["title"] == "Send the onboarding questionnaire"
    assert [a["key"] for a in fresh["access"]] == ["GSC", "GA4", "CMS", "AHREFS", "GDRIVE"]
    assert fresh["access"][2]["label"] == "CMS Access"
    assert fresh["permissions"]["manage"] is True

    # 4–5. Questionnaire: a staff draft, then the client finishes via the public link.
    draft = await world.http.put(
        f"/api/v1/onboarding/clients/{cid}/questionnaire",
        json={"answers": {"business_goals": ANSWERS["business_goals"]}},
    )
    q = draft.json()["questionnaire"]
    assert q["status"] == "none"
    assert [s["complete"] for s in q["sections"]] == [True, False, False, False, False, True]
    link = (await world.post(cid, "questionnaire/send")).json()
    token = re.search(r"/q/(\S+)$", link["url"])
    assert token is not None
    public = f"/api/v1/onboarding/questionnaire/{token.group(1)}"
    opened = (await world.http.get(public)).json()
    assert opened["client_name"] == "Acme Ltd"
    assert opened["answers"]["business_goals"]["goals"] == ["organic_traffic", "leads"]
    assert len(opened["goals"]) == 9
    saved = await world.http.put(public, json={"answers": {**ANSWERS, "past_seo": {}}})
    assert saved.status_code == 200
    incomplete = await world.http.post(public, json={"answers": {**ANSWERS, "past_seo": {}}})
    assert incomplete.status_code == 422
    assert "Past SEO Work: whether SEO was done before" in error(incomplete)
    assert (await world.http.post(public, json={"answers": ANSWERS})).status_code == 204
    assert (await world.http.get(public)).status_code == 404
    submitted = await world.detail(cid)
    assert (submitted["questionnaire"]["status"], submitted["questionnaire"]["source"]) == (
        "submitted",
        "client",
    )
    assert stage(submitted, "questionnaire") == "completed"
    assert "Acme Ltd submitted the onboarding questionnaire" in await notifications(world, am)

    # 6–7. Access: request all, receive, verify (a rejection blocks until received again).
    requested = (await world.post(cid, "access/bulk", {"status": "requested"})).json()
    assert {a["status"] for a in requested["access"]} == {"requested"}
    assert all(a["requested_at"] for a in requested["access"])
    await world.http.patch(
        f"/api/v1/onboarding/clients/{cid}/access/GSC", json={"status": "received"}
    )
    await world.act_as(pm)
    rejected = await world.http.patch(
        f"/api/v1/onboarding/clients/{cid}/access/GSC", json={"status": "rejected"}
    )
    assert rejected.json()["status"] == "blocked"
    assert "Acme Ltd: Google Search Console access was rejected" in await notifications(world, am)
    noted = await world.http.patch(
        f"/api/v1/onboarding/clients/{cid}/access/GSC/details",
        json={"notes": "Wrong property shared"},
    )
    assert noted.json()["access"][0]["notes"] == "Wrong property shared"
    await world.act_as(am)
    await world.post(cid, "access/bulk", {"status": "received"})
    again = await world.http.patch(
        f"/api/v1/onboarding/clients/{cid}/access/GSC", json={"status": "received"}
    )
    assert again.json()["status"] == "in_progress"  # no longer blocked
    added = await world.post(cid, "access", {"label": "Search Ads", "description": "Google Ads"})
    custom = next(a for a in added.json()["access"] if a["label"] == "Search Ads")
    assert (custom["key"], custom["is_custom"]) == ("SEARCH_ADS", True)
    removed = await world.http.delete(f"/api/v1/onboarding/clients/{cid}/access/SEARCH_ADS")
    assert len(removed.json()["access"]) == 5
    builtin = await world.http.delete(f"/api/v1/onboarding/clients/{cid}/access/GSC")
    assert builtin.status_code == 422
    await world.act_as(pm)
    for key in ("GSC", "GA4", "CMS", "AHREFS", "GDRIVE"):
        verified = await world.http.patch(
            f"/api/v1/onboarding/clients/{cid}/access/{key}", json={"status": "verified"}
        )
        assert verified.status_code == 200, verified.text
    access_done = verified.json()
    assert access_done["access_summary"] == {"required": 5, "verified": 5, "percent": 100}
    assert access_done["access"][0]["verified_by"]["full_name"] == "Tomas"
    assert stage(access_done, "access") == "completed"

    # 8. KPIs: targets, client confirmation; changing a target needs it again.
    await world.act_as(am)
    target_date = (datetime.now(UTC) + timedelta(days=365)).date().isoformat()
    kpi = {
        "metric": "Organic Sessions",
        "description": "Total organic sessions",
        "baseline": "10000",
        "target": "14000",
        "unit": "/ month",
        "target_date": target_date,
    }
    await world.post(cid, "kpis", kpi)
    with_two = (await world.post(cid, "kpis", {**kpi, "metric": "Qualified Leads"})).json()
    assert with_two["kpi_summary"]["not_measured"] == 2
    confirm = {"confirmed_by": "John Doe", "via": "meeting"}
    confirmed = (await world.post(cid, "kpis/confirm", confirm)).json()
    assert confirmed["kpi_summary"]["confirmed_by"] == "John Doe"
    assert step(confirmed, "kpi") == "done"
    kpi_id = confirmed["kpis"][0]["id"]
    moved = await world.http.patch(
        f"/api/v1/onboarding/clients/{cid}/kpis/{kpi_id}", json={"target": "15000"}
    )
    assert step(moved.json(), "kpi") == "progress"
    await world.post(cid, "kpis/confirm", confirm)
    tracked = await world.http.patch(
        f"/api/v1/onboarding/clients/{cid}/kpis/{kpi_id}", json={"current_value": "12500"}
    )
    first = tracked.json()["kpis"][0]
    assert (first["progress"], first["status"], first["confirmed_at"] is not None) == (
        50,
        "achieved" if first["progress"] >= 100 else first["status"],
        True,
    )
    assert first["status"] in ("on_track", "at_risk", "behind")
    notes = await world.http.put(
        f"/api/v1/onboarding/clients/{cid}/kpi-notes", json={"notes": "Reviewed quarterly"}
    )
    assert notes.json()["kpi_summary"]["notes"] == "Reviewed quarterly"

    # 9–10. Kickoffs are meetings; the internal one also needs a team.
    kickoff = await meeting(
        world,
        cid,
        "kickoff",
        attendee_ids=[str(pm.id)],
        guests=[{"name": "John Doe", "email": "john@acme.com", "organisation": "Acme"}],
        agenda="Goals, markets, access",
    )
    assert step(await world.detail(cid), "kickoff_client") == "progress"
    assert "Meeting scheduled: Kickoff Call" in await notifications(world, pm)
    done = await world.http.post(
        f"/api/v1/meetings/{kickoff['id']}/complete", json={"notes": "Goals agreed"}
    )
    assert done.json()["status"] == "completed"
    team = await world.post(
        cid,
        "team",
        {
            "user_id": str(specialist.id),
            "area": "seo",
            "role_title": "SEO Specialist",
            "responsibilities": "Audit and on-page work",
            "allocation": 50,
        },
    )
    member = team.json()["team"][0]
    assert (member["role_title"], member["area"], member["allocation"]) == (
        "SEO Specialist",
        "seo",
        50,
    )
    seo = next(c for c in team.json()["coverage"] if c["area"] == "seo")
    assert [m["full_name"] for m in seo["members"]] == ["Jordan"]
    assert "You've been added to the Acme Ltd team as SEO Specialist" in await notifications(
        world, specialist
    )
    internal = await meeting(world, cid, "internal", attendee_ids=[str(specialist.id)])
    await world.http.post(
        f"/api/v1/meetings/{internal['id']}/complete", json={"notes": "Roles agreed"}
    )
    ready = await world.detail(cid)
    assert step(ready, "kickoff_internal") == "done"
    assert stage(ready, "kickoff") == "completed"

    # 11–12. Review, completion → Active; the team hears about it.
    assert (await world.post(cid, "review")).status_code == 200
    completed = (await world.post(cid, "complete")).json()
    assert completed["status"] == "completed"
    assert completed["client"]["status"] == "active"
    assert completed["locked_reason"] == "Onboarding is completed."
    assert step(completed, "project") == "progress"
    client = await world.session.get(Client, completed["client"]["id"])
    assert client is not None
    assert client.status == "active"
    assert "Acme Ltd is onboarded — project creation is open" in await notifications(
        world, specialist
    )
    # Current KPI values stay trackable after onboarding.
    after = await world.http.patch(
        f"/api/v1/onboarding/clients/{cid}/kpis/{kpi_id}", json={"current_value": "13000"}
    )
    assert after.status_code == 200
    frozen = await world.http.patch(
        f"/api/v1/onboarding/clients/{cid}/kpis/{kpi_id}", json={"target": "20000"}
    )
    assert error(frozen) == "Onboarding is already completed."
    audit = (
        await world.session.execute(
            select(AuditLog.action).where(AuditLog.action.like("onboarding.%"))
        )
    ).scalars()
    assert "onboarding.completed" in set(audit)


async def test_completion_gates_and_on_hold(world: World) -> None:
    am = await world.user("anika@example.com", "account_manager")
    await world.act_as(am)
    cid = await world.client(am)
    early = await world.post(cid, "complete")
    assert error(early) == (
        "All required access items must be verified before onboarding can be completed."
    )
    review = await world.post(cid, "review")
    assert error(review).startswith("Review can't pass yet. Incomplete:")

    # On hold: nothing moves until the client is reactivated.
    await world.http.post(f"/api/v1/clients/{cid}/status", json={"action": "hold"})
    held = await world.detail(cid)
    assert held["locked_reason"] == "This client is on hold. Reactivate it to continue onboarding."
    assert held["permissions"]["manage"] is False
    blocked = await world.post(cid, "questionnaire/send")
    assert error(blocked) == "This client is on hold. Reactivate it to continue onboarding."
    await world.http.post(f"/api/v1/clients/{cid}/status", json={"action": "reactivate"})
    assert (await world.post(cid, "questionnaire/send")).status_code == 200

    # Staff can record the answers (complete ones only).
    partial = await world.post(cid, "questionnaire/submit", {"answers": {}})
    assert partial.status_code == 422
    recorded = (await world.post(cid, "questionnaire/submit", {"answers": ANSWERS})).json()
    assert recorded["questionnaire"]["source"] == "staff"


async def test_only_the_clients_account_manager_runs_onboarding(world: World) -> None:
    am = await world.user("anika@example.com", "account_manager")
    other_am = await world.user("omar@example.com", "account_manager")
    lead = await world.user("mei@example.com", "team_lead")
    outsider = await world.user("sam@example.com", "employee")
    await world.act_as(am)
    cid = await world.client(am)
    await world.post(cid, "team", {"user_id": str(lead.id)})

    await world.act_as(other_am)
    view = await world.detail(cid)
    assert view["permissions"]["manage"] is False
    assert (await world.post(cid, "questionnaire/send")).status_code == 403
    await world.act_as(lead)
    assert (await world.detail(cid))["permissions"]["verify_access"] is True
    await world.act_as(outsider)
    assert (await world.http.get(f"/api/v1/onboarding/clients/{cid}")).status_code == 404


async def test_board_lists_progress(world: World) -> None:
    am = await world.user("anika@example.com", "account_manager")
    await world.act_as(am)
    first = await world.client(am)
    await world.client(am, name="Beta Co", website="beta.io")
    await world.post(first, "questionnaire/submit", {"answers": ANSWERS})
    board = (await world.http.get("/api/v1/onboarding")).json()
    assert [(r["client_name"], r["progress"], r["client_status"]) for r in board] == [
        ("Acme Ltd", 38, "onboarding"),
        ("Beta Co", 23, "onboarding"),
    ]
    assert board[0]["current_step"] == "Platform access collected"


async def test_overdue_reminders_job(world: World) -> None:
    am = await world.user("anika@example.com", "account_manager")
    await world.act_as(am)
    await world.client(am)
    clock = FixedClock(datetime.now(UTC) + timedelta(days=20))
    service = OnboardingService(world.session, clock=clock, settings=make_settings())
    assert await service.remind_overdue() == {"checked": 1, "reminders": 1}
    assert await service.remind_overdue() == {"checked": 1, "reminders": 0}  # once a day
    titles = await notifications(world, am)
    assert titles == ["Acme Ltd: Send the onboarding questionnaire is overdue (+9 more overdue)"]
    clock.advance(timedelta(days=1, minutes=1))
    assert (await service.remind_overdue())["reminders"] == 1
