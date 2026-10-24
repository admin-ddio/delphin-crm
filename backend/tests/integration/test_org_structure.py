"""Organization & Role Settings end to end on PostgreSQL (Organization brief §11):
default reporting, dual functional reporting, project-mediated delivery, loop and
duplicate blocking, previews, history, role escalation protection and module scope."""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import select

from app.modules.team.models import ReportingLine
from app.platform.audit.models import AuditLog
from tests.integration.test_onboarding import World, error, world
from tests.integration.test_people import (
    department,
    designation,
    employee,
    get,
    patch,
    people_admin,
    reporting,
)
from tests.integration.test_projects import complete_onboarding, new_project

pytestmark = pytest.mark.integration

__all__ = ["world"]  # fixture re-export


def relations(detail: dict[str, Any], kind: str) -> list[tuple[str, str]]:
    return sorted(
        (r["manager"]["full_name"], r["source"])
        for r in detail["employment"]["reporting"]
        if r["kind"] == kind
    )


async def founders_and_departments(w: World) -> dict[str, dict[str, Any]]:
    """The brief's default configuration (§3, §5), built through the API."""
    await w.act_as(await people_admin(w, "setup@example.com"))
    people = {
        "ceo": await employee(
            w, "Hanumesh JK", designation_id=await designation(w, "Founder & CEO")
        ),
        "coo": await employee(
            w, "Vinay Kumar", designation_id=await designation(w, "Co-Founder & COO")
        ),
        "cofounder": await employee(
            w, "Shilpa R", designation_id=await designation(w, "Co-Founder")
        ),
        "pm": await employee(
            w,
            "Neeta W",
            department_id=await department(w, "Project Management Team"),
            designation_id=await designation(w, "Project Manager"),
        ),
    }
    for key in ("ceo", "coo", "cofounder"):
        assert (await patch(w, people[key]["id"], is_executive=True)).status_code == 200
    ceo, coo, pm = people["ceo"]["id"], people["coo"]["id"], people["pm"]["id"]
    owners = {
        "Web Development Team": [ceo],
        "Application Development Team": [ceo],
        "SEO Team": [coo],
        "Social Media Team": [coo],
        "Design Team": [ceo, coo],
    }
    for name in (
        "Web Development Team",
        "Application Development Team",
        "SEO Team",
        "Design Team",
        "Social Media Team",
        "Content Team",
        "Performance Marketing Team",
    ):
        saved = await w.http.patch(
            f"/api/v1/team/departments/{await department(w, name)}",
            json={"owner_ids": owners.get(name, []), "delivery_manager_id": pm},
        )
        assert saved.status_code == 200, saved.text
    return people


async def test_default_configuration_and_dual_reporting(world: World) -> None:
    people = await founders_and_departments(world)
    designer = await employee(
        world,
        "Priya Designer",
        department_id=await department(world, "Design Team"),
        designation_id=await designation(world, "Graphic Designer", "Design Team"),
    )
    writer = await employee(
        world, "Kiran Writer", department_id=await department(world, "Content Team")
    )
    seo = await employee(world, "Arjun SEO", department_id=await department(world, "SEO Team"))

    # Design: two functional managers from one record; delivery via the PM.
    detail = await get(world, designer["id"])
    assert relations(detail, "functional_manager") == [
        ("Hanumesh JK", "department"),
        ("Vinay Kumar", "department"),
    ]
    assert relations(detail, "project_manager") == [("Neeta W", "department")]
    assert relations(detail, "executive_escalation") == [
        ("Hanumesh JK", "department"),
        ("Vinay Kumar", "department"),
    ]
    # No direct manager: approvals fall back to the functional managers.
    assert relations(detail, "leave_approver") == [
        ("Hanumesh JK", "functional_manager"),
        ("Vinay Kumar", "functional_manager"),
    ]
    assert relations(await get(world, seo["id"]), "functional_manager") == [
        ("Vinay Kumar", "department")
    ]
    # Content's owner is configurable: none assigned yet, but delivery still via the PM.
    content = await get(world, writer["id"])
    assert relations(content, "functional_manager") == []
    assert relations(content, "project_manager") == [("Neeta W", "department")]
    # The PM is not the functional manager of the departments she delivers for.
    assert ("Neeta W", "department") not in relations(detail, "functional_manager")

    chart = (await world.http.get("/api/v1/team/org-chart")).json()
    assert [e["full_name"] for e in chart["executives"]] == [
        "Hanumesh JK",
        "Shilpa R",
        "Vinay Kumar",
    ]
    assert all(not e["relations"] for e in chart["executives"])  # no founder under another
    by_name = {d["name"]: d for d in chart["departments"]}
    assert [o["full_name"] for o in by_name["Design Team"]["owners"]] == [
        "Hanumesh JK",
        "Vinay Kumar",
    ]
    assert "No executive owner" in by_name["Content Team"]["issues"]
    assert "No executive owner" in by_name["Operations Team"]["issues"]
    assert "No default project manager" in by_name["Operations Team"]["issues"]
    assert [m["full_name"] for m in by_name["Design Team"]["members"]] == ["Priya Designer"]
    assert by_name["Content Team"]["members"][0]["issues"] == ["No functional manager"]
    member_ids = [m["id"] for d in chart["departments"] for m in d["members"]]
    assert len(member_ids) == len(set(member_ids))  # nobody duplicated
    (group,) = chart["delivery"]
    assert group["manager"]["full_name"] == "Neeta W"
    assert {p["full_name"] for p in group["members"]} == {
        "Priya Designer",
        "Kiran Writer",
        "Arjun SEO",
    }
    assert people["pm"]["department"]["name"] == "Project Management Team"


async def test_project_assignments_do_not_touch_functional_reporting(world: World) -> None:
    people = await founders_and_departments(world)
    dev = await employee(
        world, "Jordan Dev", department_id=await department(world, "Web Development Team")
    )
    second_pm = await employee(
        world, "Ravi PM", department_id=await department(world, "Project Management Team")
    )
    am = await world.user("anika@example.com", "account_manager")
    pm_user = await world.user("tomas@example.com", "project_manager")
    await world.act_as(am)
    cid = await world.client(am)
    await complete_onboarding(world, cid)
    await world.act_as(pm_user)
    project = (await new_project(world, cid, pm_user, template="blank")).json()

    # A Project Manager (org.projects.assign) changes Project Manager lines only.
    pm_line = ("project_manager", second_pm["id"], project["id"])
    saved = await reporting(world, dev["id"], pm_line)
    assert saved.status_code == 200, saved.text
    assert saved.json()["projects_only"] is True
    denied = await reporting(world, dev["id"], pm_line, ("functional_manager", people["coo"]["id"]))
    assert denied.status_code == 403
    options = (await world.http.get("/api/v1/team/project-options")).json()
    assert [o["code"] for o in options] == [project["code"]]

    await world.act_as(await world.user("org@example.com", "org_admin"))
    detail = await get(world, dev["id"])
    assert detail["employment"] is None  # HR employment details are not the org admin's
    rep = (await world.http.get(f"/api/v1/team/employees/{dev['id']}/reporting")).json()
    assert relations({"employment": {"reporting": rep["effective"]}}, "functional_manager") == [
        ("Hanumesh JK", "department")
    ]
    pms = [r for r in rep["effective"] if r["kind"] == "project_manager"]
    assert [(r["manager"]["full_name"], r["project"]["code"]) for r in pms] == [
        ("Ravi PM", project["code"])
    ]
    assert detail["department"]["name"] == "Web Development Team"
    # Several PMs at once, one per project; the same PM and project twice is refused.
    both = await reporting(world, dev["id"], pm_line, ("project_manager", people["pm"]["id"]))
    assert both.status_code == 200, both.text
    twice = await reporting(world, dev["id"], pm_line, pm_line)
    assert error(twice) == "Project manager: Ravi PM is listed twice."
    wrong_kind = await reporting(
        world, dev["id"], ("functional_manager", second_pm["id"], project["id"])
    )
    assert error(wrong_kind) == "Functional manager: only Project Manager lines can name a project."

    chart = (await world.http.get("/api/v1/team/org-chart")).json()
    groups = {g["manager"]["full_name"]: g for g in chart["delivery"]}
    assert groups["Ravi PM"]["projects"][0]["project"]["name"] == project["name"]
    assert [m["full_name"] for m in groups["Ravi PM"]["projects"][0]["members"]] == ["Jordan Dev"]
    assert "Jordan Dev" in {m["full_name"] for m in groups["Neeta W"]["members"]}

    # People without project access see that an assignment exists, not the project.
    await world.act_as(await world.user("sam@example.com", "employee"))
    chart = (await world.http.get("/api/v1/team/org-chart")).json()
    groups = {g["manager"]["full_name"]: g for g in chart["delivery"]}
    assert groups["Ravi PM"]["projects"][0]["project"]["name"] == "Restricted project"


async def test_loops_duplicates_dates_preview_and_history(world: World) -> None:
    people = await founders_and_departments(world)
    ceo, coo = people["ceo"]["id"], people["coo"]["id"]
    lead = await employee(
        world, "Mei Lead", department_id=await department(world, "SEO Team"), manager_id=coo
    )
    dev = await employee(
        world,
        "Jordan Dev",
        department_id=await department(world, "SEO Team"),
        manager_id=lead["id"],
    )

    # Loops through functional lines are blocked, inherited ones included.
    loop = await reporting(world, coo, ("functional_manager", dev["id"]))
    assert error(loop) == (
        "That would create a reporting loop: Jordan Dev already reports to Vinay Kumar."
    )
    owner_loop = await world.http.patch(
        f"/api/v1/team/departments/{await department(world, 'SEO Team')}",
        json={"owner_ids": [dev["id"]]},
    )
    assert owner_loop.status_code == 422
    two_direct = await reporting(
        world, dev["id"], ("direct_manager", lead["id"]), ("direct_manager", ceo)
    )
    assert error(two_direct) == "Only one direct manager at a time."
    future = await reporting(
        world, dev["id"], ("direct_manager", lead["id"]), effective_on="2999-01-01"
    )
    assert error(future) == "The effective date can't be in the future."

    # Preview: validated and charted, nothing saved.
    proposal = {
        "lines": [
            {"kind": "direct_manager", "manager_id": ceo},
            {"kind": "functional_manager", "manager_id": coo},
            {"kind": "performance_reviewer", "manager_id": lead["id"]},
        ]
    }
    preview = (
        await world.http.post(
            f"/api/v1/team/employees/{dev['id']}/reporting/preview", json=proposal
        )
    ).json()
    assert preview["valid"] is True
    assert [(c["kind"], c["manager"]["full_name"]) for c in preview["ended"]] == [
        ("direct_manager", "Mei Lead")
    ]
    assert {(c["kind"], c["manager"]["full_name"]) for c in preview["added"]} == {
        ("direct_manager", "Hanumesh JK"),
        ("functional_manager", "Vinay Kumar"),
        ("performance_reviewer", "Mei Lead"),
    }
    charted = next(
        m for d in preview["chart"]["departments"] for m in d["members"] if m["id"] == dev["id"]
    )
    assert ("direct_manager", "Hanumesh JK") in {
        (r["kind"], r["manager"]["full_name"]) for r in charted["relations"]
    }
    assert (await get(world, dev["id"]))["manager"]["full_name"] == "Mei Lead"  # unchanged
    bad = (
        await world.http.post(
            f"/api/v1/team/employees/{dev['id']}/reporting/preview",
            json={"lines": [{"kind": "direct_manager", "manager_id": dev["id"]}]},
        )
    ).json()
    assert bad["valid"] is False
    assert bad["errors"] == ["Direct manager: an employee can't report to themselves."]

    # Save with an effective date; ended lines stay in the history.
    saved = await world.http.put(
        f"/api/v1/team/employees/{dev['id']}/reporting",
        json={**proposal, "effective_on": str((await get(world, dev["id"]))["created_at"])[:10]},
    )
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert len(body["lines"]) == 3
    ended = [h for h in body["history"] if not h["active"]]
    assert [(h["kind"], h["manager"]["full_name"]) for h in ended] == [
        ("direct_manager", "Mei Lead")
    ]
    assert ended[0]["ends_on"] is not None
    assert ended[0]["ended_by"] == "Setup"
    # The explicit functional line replaces the department default; the reviewer is explicit.
    detail = await get(world, dev["id"])
    assert relations(detail, "functional_manager") == [("Vinay Kumar", "explicit")]
    assert relations(detail, "performance_reviewer") == [("Mei Lead", "explicit")]
    rows = (
        await world.session.execute(
            select(ReportingLine).where(ReportingLine.employee_id == dev["id"])
        )
    ).scalars()
    assert len(list(rows)) == 4  # nothing deleted
    entry = (
        await world.session.execute(select(AuditLog).where(AuditLog.action == "reporting.changed"))
    ).scalar_one()
    assert entry.changes["ended"][0]["manager"]["full_name"] == "Mei Lead"

    audit = (await world.http.get("/api/v1/team/org-audit")).json()
    assert {"reporting.changed", "department.updated"} <= {a["action"] for a in audit}


async def test_role_settings_block_escalation(world: World) -> None:
    super_admin = await world.user("root@example.com", "super_admin")
    admin = await world.user("orgadmin@example.com", "org_admin")
    staff = await world.user("jordan@example.com", "employee")
    am = await world.user("anika@example.com", "account_manager")
    await world.act_as(admin)

    overview = (await world.http.get("/api/v1/team/roles")).json()
    roles = {r["key"]: r for r in overview["roles"]}
    assert overview["can_manage"]
    assert overview["can_assign"]
    assert roles["super_admin"]["editable"] is False
    assert roles["org_admin"]["editable"] is False  # a role the admin holds
    assert roles["account_manager"]["editable"] is False  # above the admin's authority
    assert roles["employee"]["editable"] is True
    assert roles["org_admin"]["member_count"] == 1
    assert {p["module"] for p in overview["catalogue"]} >= {"Organization & roles", "Clients"}

    # Only permissions the admin holds can be granted, never full access.
    beyond = await world.http.post(
        "/api/v1/team/roles",
        json={"key": "sneaky", "name": "Sneaky", "permissions": ["clients.view_all"]},
    )
    assert error(beyond) == "You can't grant 'clients.view_all': you don't hold it yourself."
    wildcard = await world.http.post(
        "/api/v1/team/roles", json={"key": "root2", "name": "Root", "permissions": ["*"]}
    )
    assert wildcard.status_code == 403
    created = await world.http.post(
        "/api/v1/team/roles",
        json={
            "key": "org_viewer",
            "name": "Org Viewer",
            "permissions": ["org.view", "org.audit.view"],
        },
    )
    assert created.status_code == 201, created.text
    assert (
        await world.http.post(
            "/api/v1/team/roles", json={"key": "org_viewer", "name": "Again", "permissions": []}
        )
    ).status_code == 409
    own = await world.http.patch("/api/v1/team/roles/org_admin", json={"permissions": ["org.view"]})
    assert error(own) == "You can't change a role you hold."
    root = await world.http.patch("/api/v1/team/roles/super_admin", json={"name": "Nope"})
    assert root.status_code == 403
    above = await world.http.patch(
        "/api/v1/team/roles/account_manager", json={"permissions": ["org.view"]}
    )
    assert error(above) == "This role has permissions you don't hold."
    edited = await world.http.patch(
        "/api/v1/team/roles/employee",
        json={"permissions": ["org.view", "org.directory.view", "org.team.view"]},
    )
    assert edited.json()["permissions"] == ["org.directory.view", "org.team.view", "org.view"]

    # Assigning roles: never one's own, never above one's authority.
    assert (
        await world.http.put(f"/api/v1/team/users/{admin.id}/roles", json={"roles": ["employee"]})
    ).status_code == 403
    to_super = await world.http.put(
        f"/api/v1/team/users/{staff.id}/roles", json={"roles": ["super_admin"]}
    )
    assert error(to_super) == "You can't assign Super Admin: it has permissions you don't hold."
    demote_am = await world.http.put(
        f"/api/v1/team/users/{am.id}/roles", json={"roles": ["employee"]}
    )
    assert error(demote_am) == "This user holds a role above your authority."
    assigned = await world.http.put(
        f"/api/v1/team/users/{staff.id}/roles", json={"roles": ["employee", "org_viewer"]}
    )
    assert assigned.json()["roles"] == ["employee", "org_viewer"]
    users = {u["email"]: u for u in (await world.http.get("/api/v1/team/users")).json()}
    assert users["orgadmin@example.com"]["editable"] is False
    assert users["root@example.com"]["editable"] is False

    # Role changes apply on the next request; designations never grant anything.
    await world.act_as(staff)
    assert (await world.http.get("/api/v1/team/org-audit")).status_code == 200
    assert (await world.http.get("/api/v1/team/roles")).status_code == 403

    actions = [a["action"] for a in (await world.http.get("/api/v1/team/org-audit")).json()]
    assert {"role.created", "role.updated", "user.roles_changed"} <= set(actions)

    # Super Admin is unchanged and may still grant anything.
    await world.act_as(super_admin)
    granted = await world.http.patch(
        "/api/v1/team/roles/org_viewer", json={"permissions": ["clients.view_all", "org.view"]}
    )
    assert granted.status_code == 200, granted.text


async def test_module_admin_has_no_unrelated_access(world: World) -> None:
    admin = await world.user("orgadmin@example.com", "org_admin")
    hr = await world.user("vinay@example.com", "hr_admin")
    am = await world.user("anika@example.com", "account_manager")
    await world.act_as(hr)
    person = await employee(world, "Sam Lee")
    assert (await world.http.get("/api/v1/team/org-audit")).status_code == 403
    assert (await world.http.get("/api/v1/team/roles")).status_code == 403
    assert (await reporting(world, person["id"])).status_code == 403
    assert (
        await patch(world, person["id"], department_id=await department(world, "SEO Team"))
    ).status_code == 403

    await world.act_as(am)
    cid = await world.client(am)
    await world.act_as(admin)
    # Organisation settings work …
    assert (await world.http.get("/api/v1/team/org-chart")).status_code == 200
    assert (
        await patch(world, person["id"], department_id=await department(world, "SEO Team"))
    ).status_code == 200
    # … but nothing outside the module: no HR records, clients, projects or sign-ups.
    assert (await patch(world, person["id"], full_name="Renamed")).status_code == 403
    assert (
        await world.http.post("/api/v1/team/employees", json={"full_name": "X"})
    ).status_code == 403
    assert (await world.http.get("/api/v1/team/registrations")).status_code == 403
    assert (await world.http.get(f"/api/v1/clients/{cid}")).status_code in (403, 404)
    clients = (await world.http.get("/api/v1/clients")).json()
    assert clients == [] or clients.get("items", []) == []
    assert (await world.http.get(f"/api/v1/team/employees/{person['id']}")).json()[
        "personal"
    ] is None
