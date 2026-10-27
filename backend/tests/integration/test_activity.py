"""Activity log: scope, filters and pagination."""

from __future__ import annotations

from typing import Any

import pytest

from app.modules.activity.repository import area_of
from tests.integration.test_onboarding import World, world
from tests.integration.test_services import on_team

pytestmark = pytest.mark.integration

__all__ = ["world"]  # fixture re-export


async def log(w: World, **params: object) -> Any:
    response = await w.http.get("/api/v1/activity", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_areas() -> None:
    assert area_of("created") == "clients"
    assert area_of("questionnaire_sent") == "onboarding"
    assert area_of("first_project_created") == "projects"
    assert area_of("changes_requested") == "approvals"
    assert area_of("uploaded") == "documents"
    assert area_of("service_started") == "services"
    assert area_of("something_new") == "other"


async def test_scope_filters_and_pages(world: World) -> None:
    am = await world.user("anika@example.com", "account_manager")
    other_am = await world.user("omar@example.com", "account_manager")
    member = await world.user("jordan@example.com", "employee")
    stranger = await world.user("sam@example.com", "employee")
    await world.act_as(am)
    acme = await world.client(am, services=[{"service_key": "seo"}])
    await world.act_as(other_am)
    beta = await world.client(
        other_am, name="Beta Pvt", website="beta.example", services=[{"service_key": "website"}]
    )
    await on_team(world, acme, member, "seo")

    # Everyone with clients.view_all sees both clients' timelines, newest first.
    everything = await log(world)
    clients = {i["client"]["name"] for i in everything["items"]}
    assert clients == {"Acme Ltd", "Beta Pvt"}
    stamps = [i["occurred_at"] for i in everything["items"]]
    assert stamps == sorted(stamps, reverse=True)
    assert {p["full_name"] for p in everything["people"]} == {"Anika", "Omar"}

    # Filters: client, person, area.
    only_beta = await log(world, client_id=beta)
    assert {i["client"]["name"] for i in only_beta["items"]} == {"Beta Pvt"}
    by_anika = await log(world, person_id=str(am.id))
    assert {i["actor"]["full_name"] for i in by_anika["items"]} == {"Anika"}
    services = await log(world, area="services")
    assert sorted(i["summary"] for i in services["items"]) == [
        "Services chosen: SEO",
        "Services chosen: SEO-friendly Website",
    ]

    # Pages: one at a time until the end.
    seen: list[str] = []
    cursor = None
    while True:
        page = await log(world, limit=1, **({"before": cursor} if cursor else {}))
        seen += [i["id"] for i in page["items"]]
        cursor = page["next_before"]
        if cursor is None:
            break
    assert seen == [i["id"] for i in everything["items"]]
    assert (
        await world.http.get("/api/v1/activity", params={"before": "nonsense"})
    ).status_code == 422

    # Team members see their clients only; others see nothing.
    await world.act_as(member)
    assert {i["client"]["name"] for i in (await log(world))["items"]} == {"Acme Ltd"}
    await world.act_as(stranger)
    assert (await log(world))["items"] == []
