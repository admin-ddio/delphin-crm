"""Services and retainers end to end on PostgreSQL (services plan, 2026-10-27)."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import update

from app.core.clock import FixedClock, SystemClock, business_today
from app.modules.clients.models import ClientTeamMember
from app.modules.services.models import ServiceEngagement
from app.modules.services.service import ServicesService
from app.modules.team.models import Department, Employee
from app.platform.identity.models import User
from tests.integration.test_onboarding import World, error, step, world
from tests.integration.test_projects import complete_onboarding

pytestmark = pytest.mark.integration

__all__ = ["world"]  # fixture re-export


async def services_of(w: World, client_id: str) -> list[dict[str, Any]]:
    response = await w.http.get("/api/v1/services", params={"client_id": client_id})
    assert response.status_code == 200, response.text
    return list(response.json()["items"])


async def service(w: World, client_id: str, key: str) -> dict[str, Any]:
    return next(s for s in await services_of(w, client_id) if s["service"]["key"] == key)


async def start(w: World, service_id: str, manager: User, start_date: date) -> Any:
    return await w.http.post(
        f"/api/v1/services/{service_id}/start",
        json={"manager_id": str(manager.id), "start_date": start_date.isoformat()},
    )


async def on_team(w: World, client_id: str, user: User, area: str) -> None:
    w.session.add(ClientTeamMember(client_id=uuid.UUID(client_id), user_id=user.id, area=area))
    await w.session.flush()


def months_ago(n: int) -> date:
    first = business_today(SystemClock()).replace(day=1)
    for _ in range(n):
        first = (first - timedelta(days=1)).replace(day=1)
    return first


async def test_services_are_chosen_at_creation(world: World) -> None:
    am = await world.user("anika@example.com", "account_manager")
    await world.act_as(am)

    missing = await world.http.post(
        "/api/v1/clients",
        json={
            "name": "No Services Ltd",
            "industry": "Retail",
            "contact_name": "Pat",
            "contact_designation": "CEO",
            "contact_email": "pat@nos.example",
            "contact_phone": "+91 98765 43210",
            "contract_start": "2026-05-01",
            "contract_end": "2027-04-30",
            "account_manager_id": str(am.id),
            "services": [],
        },
    )
    assert missing.status_code == 422
    twice = await world.http.post(
        "/api/v1/clients",
        json={
            "name": "Twice Ltd",
            "website": "twice.example",
            "industry": "Retail",
            "contact_name": "Pat",
            "contact_designation": "CEO",
            "contact_email": "pat@twice.example",
            "contact_phone": "+91 98765 43210",
            "contract_start": "2026-05-01",
            "contract_end": "2027-04-30",
            "account_manager_id": str(am.id),
            "services": [{"service_key": "seo"}, {"service_key": "seo"}],
        },
    )
    assert twice.status_code == 409

    cid = await world.client(
        am,
        services=[
            {"service_key": "seo", "fee": "45000"},
            {"service_key": "website", "fee": "150000"},
        ],
    )
    rows = await services_of(world, cid)
    assert [(s["service"]["key"], s["status"], s["fee"]) for s in rows] == [
        ("seo", "planned", "45000.00"),
        ("website", "planned", "150000.00"),
    ]
    assert all(s["code"].startswith("SRV-") for s in rows)

    # One SEO and one Social retainer at a time; projects may repeat.
    again = await world.http.post(
        f"/api/v1/services/clients/{cid}", json={"services": [{"service_key": "seo"}]}
    )
    assert error(again) == "Acme Ltd already has a SEO retainer. A client can have one at a time."
    added = await world.http.post(
        f"/api/v1/services/clients/{cid}",
        json={"services": [{"service_key": "social_media"}, {"service_key": "website"}]},
    )
    assert added.status_code == 201, added.text
    assert sorted(s["service"]["key"] for s in added.json()) == [
        "seo",
        "social_media",
        "website",
        "website",
    ]
    unknown = await world.http.post(
        f"/api/v1/services/clients/{cid}", json={"services": [{"service_key": "ppc"}]}
    )
    assert unknown.status_code == 422


async def test_onboarding_checklist_follows_the_services(world: World) -> None:
    am = await world.user("anika@example.com", "account_manager")
    await world.act_as(am)
    cid = await world.client(
        am, services=[{"service_key": "social_media"}, {"service_key": "mobile_app"}]
    )
    detail = await world.detail(cid)
    keys = [a["key"] for a in detail["access"]]
    assert keys == [
        "META_BS",
        "INSTAGRAM",
        "FB_PAGE",
        "LINKEDIN",
        "APPLE_DEV",
        "PLAY_CONSOLE",
        "FIREBASE",
        "REPO",
        "GDRIVE",
    ]
    assert "GSC" not in keys
    # A service added while onboarding is open extends the checklist (no duplicates).
    await world.http.post(
        f"/api/v1/services/clients/{cid}", json={"services": [{"service_key": "web_app"}]}
    )
    keys = [a["key"] for a in (await world.detail(cid))["access"]]
    assert keys[-2:] == ["CLOUD", "DOMAIN_DNS"]
    assert keys.count("REPO") == 1
    assert step(await world.detail(cid), "project") == "todo"


async def test_starting_a_project_service(world: World) -> None:
    am = await world.user("anika@example.com", "account_manager")
    pm = await world.user("neeta@example.com", "project_manager")
    dev = await world.user("jordan@example.com", "employee")
    await world.act_as(am)
    cid = await world.client(am, services=[{"service_key": "website"}])
    website = await service(world, cid, "website")

    blocked = await start(world, website["id"], pm, date(2026, 3, 2))
    assert error(blocked) == "Services can only start after client onboarding is completed."

    # Default PM: the delivering department's delivery manager (org structure).
    employee = Employee(code="DD-9001", full_name="Neeta W", user_id=pm.id, status="active")
    world.session.add(employee)
    await world.session.flush()
    await world.session.execute(
        update(Department)
        .where(Department.name == "Web Development Team")
        .values(delivery_manager_id=employee.id)
    )
    await complete_onboarding(world, cid)
    options = (await world.http.get(f"/api/v1/services/{website['id']}/start-options")).json()
    assert options["default_manager"]["full_name"] == "Neeta"
    assert options["onboarding_completed"] is True

    await on_team(world, cid, dev, "development")
    started = await start(world, website["id"], pm, date(2026, 3, 2))  # a Monday
    assert started.status_code == 200, started.text
    body = started.json()
    assert body["status"] == "active"
    assert body["project"]["code"].startswith("PRJ-")
    titles = [t["title"] for t in body["tasks"]]
    assert titles[0] == "Discovery & requirements"
    assert len(titles) == 8
    by_title = {t["title"]: t for t in body["tasks"]}
    # 2 Mar + 0 + 5 = 7 Mar (Saturday) → Monday 9 Mar.
    assert by_title["Discovery & requirements"]["due_date"] == "2026-03-09"
    assert by_title["Development"]["assignee"]["full_name"] == "Jordan"
    assert by_title["UI design"]["requires_client_approval"] is True
    assert body["progress"] == {"total": 8, "done": 0}
    again = await start(world, website["id"], pm, date(2026, 3, 2))
    assert error(again) == "This service is active; only planned services start."
    assert step(await world.detail(cid), "project") == "done"


async def test_retainer_months_are_generated_once(world: World) -> None:
    am = await world.user("anika@example.com", "account_manager")
    pm = await world.user("tomas@example.com", "project_manager")
    specialist = await world.user("jordan@example.com", "employee")
    await world.act_as(am)
    cid = await world.client(am, services=[{"service_key": "seo", "fee": "45000"}])
    await complete_onboarding(world, cid)
    await on_team(world, cid, specialist, "seo")
    seo = await service(world, cid, "seo")

    # The month it starts gets the setup tasks only.
    fresh = await start(world, seo["id"], pm, business_today(SystemClock()))
    assert fresh.status_code == 200, fresh.text
    assert len(fresh.json()["tasks"]) == 0  # this month's monthly tasks: none yet
    none_yet = await world.http.post(f"/api/v1/services/{seo['id']}/generate")
    assert none_yet.json()["created"] == 0

    # A retainer that started two months ago generates this month's six tasks, once.
    await world.session.execute(
        update(ServiceEngagement)
        .where(ServiceEngagement.id == uuid.UUID(seo["id"]))
        .values(start_date=months_ago(2))
    )
    first = await world.http.post(f"/api/v1/services/{seo['id']}/generate")
    assert first.json()["created"] == 6, first.text
    second = await world.http.post(f"/api/v1/services/{seo['id']}/generate")
    assert second.json() == {**first.json(), "created": 0, "skipped": 6}

    workspace = (await world.http.get(f"/api/v1/services/{seo['id']}")).json()
    assert len(workspace["tasks"]) == 6
    assert all(t["due_date"] for t in workspace["tasks"])
    assert all(date.fromisoformat(t["due_date"]).weekday() < 5 for t in workspace["tasks"])
    keyword = next(t for t in workspace["tasks"] if t["title"].startswith("Keyword tracking"))
    assert keyword["assignee"]["full_name"] == "Jordan"
    plan = next(t for t in workspace["tasks"] if t["title"].startswith("Next month content"))
    assert plan["assignee"] is None  # no content specialist on the team
    assert workspace["history"] == [{"period": workspace["current_period"], "total": 6, "done": 0}]
    assert workspace["fee"] == "45000.00"

    # Paused retainers generate nothing; the monthly job covers the next month.
    paused = await world.http.post(f"/api/v1/services/{seo['id']}/pause")
    assert paused.json()["status"] == "paused"
    refused = await world.http.post(f"/api/v1/services/{seo['id']}/generate")
    assert error(refused) == "Only active retainers generate monthly tasks."
    await world.http.post(f"/api/v1/services/{seo['id']}/resume")
    next_month = (datetime.now(UTC).replace(day=1) + timedelta(days=40)).replace(day=3)
    job = ServicesService(world.session, clock=FixedClock(next_month))
    assert await job.generate_all() == {"retainers": 1, "created": 6, "skipped": 0}
    assert await job.generate_all() == {"retainers": 1, "created": 0, "skipped": 6}

    ended = await world.http.post(f"/api/v1/services/{seo['id']}/complete")
    assert ended.json()["status"] == "completed"
    # A new SEO retainer is possible once the old one has ended.
    renewed = await world.http.post(
        f"/api/v1/services/clients/{cid}", json={"services": [{"service_key": "seo"}]}
    )
    assert renewed.status_code == 201


async def test_money_scope_and_permissions(world: World) -> None:
    am = await world.user("anika@example.com", "account_manager")
    other_am = await world.user("omar@example.com", "account_manager")
    pm = await world.user("tomas@example.com", "project_manager")
    finance = await world.user("fin@example.com", "finance")
    member = await world.user("jordan@example.com", "employee")
    stranger = await world.user("sam@example.com", "employee")
    await world.act_as(am)
    cid = await world.client(am, services=[{"service_key": "seo", "fee": "45000"}])
    await on_team(world, cid, member, "seo")
    seo = await service(world, cid, "seo")

    await world.act_as(pm)
    as_pm = (await world.http.get("/api/v1/services")).json()
    assert as_pm["items"][0]["fee"] is None
    assert as_pm["tiles"]["contracted_monthly"] is None
    await world.act_as(finance)
    assert (await world.http.get("/api/v1/services")).json()["items"][0]["fee"] == "45000.00"
    await world.act_as(member)
    assert (await world.http.get(f"/api/v1/services/{seo['id']}")).json()["fee"] is None
    await world.act_as(stranger)
    assert (await world.http.get(f"/api/v1/services/{seo['id']}")).status_code == 404
    assert (await world.http.get("/api/v1/services")).json()["items"] == []
    await world.act_as(other_am)  # sees every client, but isn't this client's AM
    await complete_onboarding(world, cid)
    denied = await start(world, seo["id"], pm, date(2026, 3, 2))
    assert error(denied) == "Only the client's Account Manager can change its services."
    await world.act_as(member)
    assert (await world.http.post(f"/api/v1/services/{seo['id']}/pause")).status_code == 403


async def test_template_editing(world: World) -> None:
    am = await world.user("anika@example.com", "account_manager")
    pm = await world.user("tomas@example.com", "project_manager")
    await world.act_as(pm)
    current = (await world.http.get("/api/v1/services/types/social_media/templates")).json()
    assert current["can_edit"] is True
    monthly = [t for t in current["tasks"] if t["phase"] == "monthly"]
    assert [t["day_of_month"] for t in monthly] == [1, 5, 15, 20, 25]

    keep = [
        {
            k: t[k]
            for k in (
                "id",
                "phase",
                "title",
                "day_of_month",
                "start_offset_days",
                "duration_days",
                "requires_review",
                "requires_client_approval",
                "area",
            )
        }
        for t in current["tasks"]
        if t["title"] != "Community management check-in"
    ]
    keep.append({"phase": "monthly", "title": "Ad hoc reels", "day_of_month": 18, "area": "social"})
    saved = await world.http.put(
        "/api/v1/services/types/social_media/templates", json={"tasks": keep}
    )
    assert saved.status_code == 200, saved.text
    titles = [t["title"] for t in saved.json()["tasks"] if t["phase"] == "monthly"]
    assert "Community management check-in" not in titles
    assert "Ad hoc reels" in titles

    bad = await world.http.put(
        "/api/v1/services/types/social_media/templates",
        json={"tasks": [{"phase": "monthly", "title": "No day"}]},
    )
    assert bad.status_code == 422
    wrong_phase = await world.http.put(
        "/api/v1/services/types/website/templates",
        json={"tasks": [{"phase": "monthly", "title": "X", "day_of_month": 3}]},
    )
    assert error(wrong_phase) == "SEO-friendly Website templates have delivery tasks only."
    await world.act_as(am)
    assert (
        await world.http.put("/api/v1/services/types/seo/templates", json={"tasks": []})
    ).status_code == 403
    types = (await world.http.get("/api/v1/services/types")).json()
    assert [(t["key"], t["kind"]) for t in types] == [
        ("seo", "retainer"),
        ("social_media", "retainer"),
        ("website", "project"),
        ("web_app", "project"),
        ("mobile_app", "project"),
    ]
