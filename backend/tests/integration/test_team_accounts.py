"""Team & Roles hub: accounts, invitations, deactivation, authority (services plan)."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.platform.audit.models import AuditLog
from app.platform.identity.models import User
from tests.integration.test_onboarding import World, error, world
from tests.integration.test_people import employee, people_admin

pytestmark = pytest.mark.integration

__all__ = ["world"]  # fixture re-export


async def accounts(w: World) -> dict[str, dict[str, object]]:
    response = await w.http.get("/api/v1/team/accounts")
    assert response.status_code == 200, response.text
    return {a["email"]: a for a in response.json()["accounts"]}


async def test_accounts_list_with_roles_status_and_workload(world: World) -> None:
    root = await world.user("root@example.com", "super_admin")
    lead = await world.user("mei@example.com", "team_lead")
    staff = await world.user("jordan@example.com", "employee")
    pending = User(email="new@example.com", full_name="New Person", is_active=True)
    world.session.add(pending)
    await world.session.flush()

    await world.act_as(root)
    rows = await accounts(world)
    assert rows["root@example.com"]["is_me"] is True
    assert rows["root@example.com"]["editable"] is False  # never yourself
    assert rows["mei@example.com"]["roles"] == ["team_lead"]
    assert rows["mei@example.com"]["status"] == "invited"  # never signed in
    assert rows["new@example.com"]["status"] == "pending"
    assert rows["jordan@example.com"]["open_tasks"] == 0

    # Team leads see the hub (org.team.view); employees don't.
    await world.act_as(lead)
    overview = (await world.http.get("/api/v1/team/accounts")).json()
    assert overview["can_invite"] is False
    assert all(a["editable"] is False for a in overview["accounts"])
    await world.act_as(staff)
    assert (await world.http.get("/api/v1/team/accounts")).status_code == 403


async def test_invite_link_and_authority(world: World) -> None:
    root = await world.user("root@example.com", "super_admin")
    await world.act_as(await people_admin(world, "hr@example.com"))
    person = await employee(world, "Kiran Writer")

    await world.act_as(root)
    invited = await world.http.post(
        "/api/v1/team/accounts/invite",
        json={
            "email": "kiran@delphin.example",
            "full_name": "Kiran Writer",
            "roles": ["employee", "team_lead"],
            "employee_id": person["id"],
        },
    )
    assert invited.status_code == 201, invited.text
    body = invited.json()
    assert body["setup_link"].startswith("https://auth.example/reset?email=kiran@delphin.example")
    assert body["account"]["roles"] == ["employee", "team_lead"]
    assert body["account"]["employee"]["full_name"] == "Kiran Writer"
    again = await world.http.post(
        "/api/v1/team/accounts/invite",
        json={"email": "kiran@delphin.example", "full_name": "Kiran", "roles": ["employee"]},
    )
    assert again.status_code == 409
    linked = await world.http.post(
        "/api/v1/team/accounts/invite",
        json={
            "email": "other@delphin.example",
            "full_name": "Other",
            "roles": ["employee"],
            "employee_id": person["id"],
        },
    )
    assert error(linked) == "Kiran Writer already has a sign-in account."

    # users.manage can be granted to a custom role; it still can't give more than it holds.
    created = await world.http.post(
        "/api/v1/team/roles",
        json={"key": "people_ops", "name": "People Ops", "permissions": ["users.manage"]},
    )
    assert created.status_code == 201, created.text
    ops = await world.user("ops@example.com", "employee")
    await world.http.put(
        f"/api/v1/team/users/{ops.id}/roles", json={"roles": ["employee", "people_ops"]}
    )
    await world.act_as(ops)
    above = await world.http.post(
        "/api/v1/team/accounts/invite",
        json={"email": "x@delphin.example", "full_name": "X", "roles": ["account_manager"]},
    )
    assert error(above) == ("You can't give Account Manager: it has permissions you don't hold.")
    audit = (
        await world.session.execute(select(AuditLog).where(AuditLog.action == "user.invited"))
    ).scalar_one()
    assert audit.changes["roles"] == ["employee", "team_lead"]


async def test_deactivate_and_reactivate(world: World) -> None:
    root = await world.user("root@example.com", "super_admin")
    other_root = await world.user("root2@example.com", "super_admin")
    staff = await world.user("jordan@example.com", "employee")
    hr = await world.user("hr@example.com", "hr_admin")

    await world.act_as(hr)  # no users.manage
    denied = await world.http.post(f"/api/v1/team/accounts/{staff.id}/deactivate")
    assert denied.status_code == 403

    await world.act_as(root)
    own = await world.http.post(f"/api/v1/team/accounts/{root.id}/deactivate")
    assert error(own) == "You can't deactivate or reactivate your own account."
    off = await world.http.post(f"/api/v1/team/accounts/{staff.id}/deactivate")
    assert off.json()["status"] == "deactivated"
    on = await world.http.post(f"/api/v1/team/accounts/{staff.id}/reactivate")
    assert on.json()["status"] == "invited"

    # A custom role with users.manage can't touch a Super Admin.
    await world.http.post(
        "/api/v1/team/roles",
        json={"key": "people_ops", "name": "People Ops", "permissions": ["users.manage"]},
    )
    ops = await world.user("ops@example.com", "employee")
    await world.http.put(
        f"/api/v1/team/users/{ops.id}/roles", json={"roles": ["employee", "people_ops"]}
    )
    await world.act_as(ops)
    above = await world.http.post(f"/api/v1/team/accounts/{other_root.id}/deactivate")
    assert error(above) == "This account holds a role above your authority."
    actions = {
        a
        for (a,) in (
            await world.session.execute(
                select(AuditLog.action).where(AuditLog.action.like("user.%activated"))
            )
        ).all()
    }
    assert actions == {"user.deactivated", "user.reactivated"}
