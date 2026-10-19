"""People core end to end on PostgreSQL: departments, directory, profiles, hierarchy."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from sqlalchemy import select

from app.platform.audit.models import AuditLog
from app.platform.identity.models import User
from tests.integration.test_onboarding import World, error, world
from tests.integration.test_projects import complete_onboarding, new_project

pytestmark = pytest.mark.integration

__all__ = ["world"]  # fixture re-export

SEEDED = [
    "Content Writers Team",
    "Design Team",
    "Development Team",
    "Operations Team",
    "SEO Team",
    "Social Media Team",
]


async def department(w: World, name: str) -> str:
    rows = (await w.http.get("/api/v1/team/departments")).json()
    return str(next(d["id"] for d in rows if d["name"] == name))


async def designation(w: World, name: str) -> str:
    rows = (await w.http.get("/api/v1/team/designations")).json()
    found = next((d["id"] for d in rows if d["name"] == name), None)
    if found:
        return str(found)
    created = await w.http.post("/api/v1/team/designations", json={"name": name})
    return str(created.json()["id"])


async def employee(w: World, name: str, **fields: Any) -> dict[str, Any]:
    response = await w.http.post("/api/v1/team/employees", json={"full_name": name, **fields})
    assert response.status_code == 201, response.text
    return dict(response.json())


async def get(w: World, employee_id: str) -> dict[str, Any]:
    response = await w.http.get(f"/api/v1/team/employees/{employee_id}")
    assert response.status_code == 200, response.text
    return dict(response.json())


async def patch(w: World, employee_id: str, **body: Any) -> httpx.Response:
    return await w.http.patch(f"/api/v1/team/employees/{employee_id}", json=body)


async def test_departments_and_designations(world: World) -> None:
    hr = await world.user("vinay@example.com", "hr_admin")
    staff = await world.user("jordan@example.com", "employee")
    await world.act_as(staff)
    rows = (await world.http.get("/api/v1/team/departments")).json()
    assert [d["name"] for d in rows] == SEEDED
    assert all(d["head"] is None and d["headcount"] == 0 for d in rows)
    denied = await world.http.post("/api/v1/team/departments", json={"name": "Sales"})
    assert denied.status_code == 403
    names = {d["name"] for d in (await world.http.get("/api/v1/team/designations")).json()}
    assert names == {"Founder & CEO", "COO", "Co-Founder", "Project Manager"}

    await world.act_as(hr)
    sales = (await world.http.post("/api/v1/team/departments", json={"name": "Sales"})).json()
    duplicate = await world.http.post("/api/v1/team/departments", json={"name": "seo team"})
    assert duplicate.status_code == 409
    lead = await employee(world, "Mei Chen", department_id=sales["id"])
    headed = await world.http.patch(
        f"/api/v1/team/departments/{sales['id']}", json={"head_id": lead["id"]}
    )
    assert (headed.json()["head"]["full_name"], headed.json()["headcount"]) == ("Mei Chen", 1)
    busy = await world.http.patch(
        f"/api/v1/team/departments/{sales['id']}", json={"is_active": False}
    )
    assert error(busy) == "Move the department's 1 employee(s) before deactivating it."
    await patch(world, lead["id"], department_id=await department(world, "SEO Team"))
    closed = await world.http.patch(
        f"/api/v1/team/departments/{sales['id']}", json={"is_active": False}
    )
    assert closed.json()["is_active"] is False
    moved = await patch(world, lead["id"], department_id=sales["id"])
    assert error(moved) == "Choose an active department."

    seo_writer = await world.http.post("/api/v1/team/designations", json={"name": "SEO Writer"})
    assert seo_writer.status_code == 201
    again = await world.http.post("/api/v1/team/designations", json={"name": "seo writer"})
    assert again.status_code == 409
    renamed = await world.http.patch(
        f"/api/v1/team/designations/{seo_writer.json()['id']}", json={"name": "SEO Copywriter"}
    )
    assert renamed.json()["name"] == "SEO Copywriter"


async def test_create_directory_and_visibility(world: World) -> None:
    hr = await world.user("vinay@example.com", "hr_admin")
    ceo_user = await world.user("hanumesh@example.com", "super_admin")
    lead_user = await world.user("mei@example.com", "team_lead")
    dev_user = await world.user("jordan@example.com", "employee")
    other_user = await world.user("sam@example.com", "employee")
    await world.act_as(hr)
    seo = await department(world, "SEO Team")

    ceo = await employee(
        world,
        "Hanumesh JK",
        designation_id=await designation(world, "Founder & CEO"),
        user_id=str(ceo_user.id),
        status="active",
    )
    assert ceo["code"] == "DD-0001"
    lead = await employee(
        world,
        "Mei Chen",
        department_id=seo,
        manager_id=ceo["id"],
        user_id=str(lead_user.id),
        official_email="mei@delphin.example",
        employment_type="full_time",
        work_arrangement="hybrid",
        joining_date="2026-01-05",
    )
    dev = await employee(
        world,
        "Jordan Blake",
        department_id=seo,
        manager_id=lead["id"],
        user_id=str(dev_user.id),
        designation_id=await designation(world, "SEO Specialist"),
    )
    other = await employee(world, "Sam Lee", user_id=str(other_user.id))
    assert dev["code"] == "DD-0003"
    assert dev["manager"]["full_name"] == "Mei Chen"
    assert dev["status"] == "onboarding"
    assert dev["employment"]["effective_leave_approver"]["full_name"] == "Mei Chen"
    assert (await get(world, lead["id"]))["direct_reports"][0]["full_name"] == "Jordan Blake"

    # Unique e-mail and account links; no duplicate accounts.
    taken = await world.http.post(
        "/api/v1/team/employees", json={"full_name": "X", "official_email": "MEI@delphin.example"}
    )
    assert taken.status_code == 409
    linked = await world.http.post(
        "/api/v1/team/employees", json={"full_name": "X", "user_id": str(dev_user.id)}
    )
    assert error(linked) == "That account is already linked to another employee."
    options = (await world.http.get("/api/v1/team/employees/user-options")).json()
    assert str(hr.id) in {o["id"] for o in options}
    assert str(dev_user.id) not in {o["id"] for o in options}

    # Everyone sees the directory; employment and personal details are restricted.
    await world.act_as(other_user)
    directory = (await world.http.get("/api/v1/team/employees")).json()
    assert [e["full_name"] for e in directory] == [
        "Hanumesh JK",
        "Jordan Blake",
        "Mei Chen",
        "Sam Lee",
    ]
    found = (await world.http.get("/api/v1/team/employees", params={"q": "dd-0003"})).json()
    assert [e["full_name"] for e in found] == ["Jordan Blake"]
    in_seo = (await world.http.get("/api/v1/team/employees", params={"department_id": seo})).json()
    assert len(in_seo) == 2
    stranger = await get(world, dev["id"])
    assert (stranger["employment"], stranger["personal"]) == (None, None)
    assert (await world.http.get(f"/api/v1/team/employees/{dev['id']}/history")).status_code == 403
    assert (await world.http.get("/api/v1/team/employees/user-options")).status_code == 403
    me = await get(world, other["id"])
    assert me["is_me"] is True
    assert me["employment"] is not None
    assert me["personal"] is not None

    # Managers up the chain see employment, not personal details.
    for viewer in (lead_user, ceo_user):
        await world.act_as(viewer)
        seen = await get(world, dev["id"])
        assert seen["employment"] is not None
        assert seen["personal"] is None or viewer is ceo_user  # Super Admin sees everything
    await world.act_as(dev_user)
    assert (await get(world, lead["id"]))["employment"] is None  # not upward

    # Dotted lines and department heads see employment too.
    await world.act_as(hr)
    dotted = await world.http.post(
        f"/api/v1/team/employees/{dev['id']}/dotted-lines", json={"manager_id": other["id"]}
    )
    assert dotted.json()["employment"]["dotted_lines"][0]["manager"]["full_name"] == "Sam Lee"
    again = await world.http.post(
        f"/api/v1/team/employees/{dev['id']}/dotted-lines", json={"manager_id": other["id"]}
    )
    assert again.status_code == 409
    await world.act_as(other_user)
    assert (await get(world, dev["id"]))["employment"] is not None
    await world.act_as(hr)
    line_id = dotted.json()["employment"]["dotted_lines"][0]["id"]
    ended = await world.http.delete(f"/api/v1/team/employees/{dev['id']}/dotted-lines/{line_id}")
    assert ended.json()["employment"]["dotted_lines"] == []
    await world.http.patch(f"/api/v1/team/departments/{seo}", json={"head_id": other["id"]})
    await world.act_as(other_user)
    assert (await get(world, dev["id"]))["employment"] is not None


async def test_reporting_changes_history_and_rules(world: World) -> None:
    hr = await world.user("vinay@example.com", "hr_admin")
    await world.act_as(hr)
    ceo = await employee(world, "Hanumesh JK")
    coo = await employee(world, "Vinay Kumar", manager_id=ceo["id"])
    pm = await employee(world, "Neeta W", manager_id=coo["id"])

    loop = await patch(world, ceo["id"], manager_id=pm["id"])
    assert error(loop) == (
        "That would create a reporting loop: Neeta W already reports to Hanumesh JK."
    )
    assert error(await patch(world, pm["id"], manager_id=pm["id"])) == (
        "An employee can't report to themselves."
    )
    moved = await patch(
        world,
        pm["id"],
        manager_id=ceo["id"],
        status="active",
        work_arrangement="remote",
        leave_approver_id=coo["id"],
    )
    assert moved.status_code == 200, moved.text
    detail = moved.json()
    assert detail["manager"]["full_name"] == "Hanumesh JK"
    assert detail["employment"]["effective_leave_approver"]["full_name"] == "Vinay Kumar"
    unmanaged = (await patch(world, pm["id"], manager_id=None)).json()
    assert unmanaged["manager"] is None
    exited = await patch(world, pm["id"], status="exited")
    assert error(exited) == "Exits go through offboarding, which arrives in a later phase."
    own_approver = await patch(world, pm["id"], leave_approver_id=pm["id"])
    assert error(own_approver) == "An employee can't approve their own leave."
    assert (await patch(world, pm["id"], full_name="  ")).status_code == 422

    history = (await world.http.get(f"/api/v1/team/employees/{pm['id']}/history")).json()
    summaries = [h["summary"] for h in history]
    assert "Reporting manager: Vinay Kumar → Hanumesh JK" in summaries
    assert "Reporting manager: Hanumesh JK → —" in summaries
    assert "Status: Onboarding → Active" in summaries
    assert "Work arrangement: — → Remote" in summaries
    assert summaries[-1] == "Employee record created: reports to Vinay Kumar"
    assert {h["actor"] for h in history} == {"Vinay"}
    assert (await world.http.get("/api/v1/team/employees/" + "0" * 32)).status_code == 404


async def test_personal_details(world: World) -> None:
    hr = await world.user("vinay@example.com", "hr_admin")
    me_user = await world.user("jordan@example.com", "employee")
    peer_user = await world.user("sam@example.com", "employee")
    await world.act_as(hr)
    me = await employee(world, "Jordan Blake", user_id=str(me_user.id))
    await employee(world, "Sam Lee", user_id=str(peer_user.id))

    await world.act_as(peer_user)
    denied = await world.http.patch(
        f"/api/v1/team/employees/{me['id']}/personal", json={"phone": "+91 1"}
    )
    assert denied.status_code == 403

    await world.act_as(me_user)
    saved = await world.http.patch(
        f"/api/v1/team/employees/{me['id']}/personal",
        json={
            "preferred_name": "Jo",
            "phone": "+91 98450 00000",
            "emergency_name": "Alex Blake",
            "emergency_relationship": "Sibling",
            "emergency_phone": "+91 98450 11111",
        },
    )
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert (body["preferred_name"], body["personal"]["emergency_name"]) == ("Jo", "Alex Blake")
    assert (await patch(world, me["id"], full_name="Nope")).status_code == 403

    await world.act_as(hr)
    assert (await get(world, me["id"]))["personal"]["phone"] == "+91 98450 00000"
    audit = (
        await world.session.execute(
            select(AuditLog).where(AuditLog.action == "employee.personal_updated")
        )
    ).scalar_one()
    # Only which fields changed is recorded, never the personal values.
    assert audit.changes == {
        "fields": [
            "preferred_name",
            "phone",
            "emergency_name",
            "emergency_relationship",
            "emergency_phone",
        ]
    }
    history = (await world.http.get(f"/api/v1/team/employees/{me['id']}/history")).json()
    assert "98450" not in str(history)


async def test_workload_filter_on_tasks(world: World) -> None:

    am = await world.user("anika@example.com", "account_manager")
    pm = await world.user("tomas@example.com", "project_manager")
    dev: User = await world.user("jordan@example.com", "employee")
    await world.act_as(am)
    cid = await world.client(am)
    await complete_onboarding(world, cid)
    await world.act_as(pm)
    project = (await new_project(world, cid, pm, template="blank")).json()
    for title, who in (("Audit", dev), ("Plan", pm)):
        await world.http.post(
            "/api/v1/tasks",
            json={"project_id": project["id"], "title": title, "assignee_id": str(who.id)},
        )
    work = (
        await world.http.get("/api/v1/tasks", params={"view": "all", "assignee_id": str(dev.id)})
    ).json()
    assert [t["title"] for t in work] == ["Audit"]
