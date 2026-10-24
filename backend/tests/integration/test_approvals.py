"""Review and approval workflow end to end on PostgreSQL."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from sqlalchemy import func, select

from app.modules.approvals.models import Approval
from app.platform.identity.models import User
from tests.integration.test_onboarding import World, error, world
from tests.integration.test_projects import complete_onboarding, move, new_project

pytestmark = pytest.mark.integration

__all__ = ["world"]  # fixture re-export


async def setup_task(
    w: World, am: User, pm: User, assignee: User, **task: Any
) -> tuple[str, dict[str, Any]]:
    await w.act_as(am)
    cid = await w.client(am)
    await complete_onboarding(w, cid)
    await w.act_as(pm)
    project = (await new_project(w, cid, pm, template="blank")).json()
    created = await w.http.post(
        "/api/v1/tasks",
        json={
            "project_id": project["id"],
            "title": "Technical fixes roadmap",
            "assignee_id": str(assignee.id),
            **task,
        },
    )
    assert created.status_code == 201, created.text
    return cid, created.json()


async def submit(
    w: World, task_id: str, note: str | None = "Roadmap ready", **extra: Any
) -> httpx.Response:
    return await w.http.post(
        "/api/v1/approvals/submit", json={"task_id": task_id, "note": note, **extra}
    )


async def decide(w: World, approval_id: str, **body: Any) -> httpx.Response:
    return await w.http.post(f"/api/v1/approvals/{approval_id}/decision", json=body)


async def test_internal_then_client_approval(world: World) -> None:
    am = await world.user("anika@example.com", "account_manager")
    pm = await world.user("tomas@example.com", "project_manager")
    dev = await world.user("jordan@example.com", "employee")
    cid, task = await setup_task(world, am, pm, dev, requires_client_approval=True)
    tid = task["id"]

    await world.act_as(dev)
    early = await submit(world, tid)
    assert early.status_code == 422
    assert error(early) == "Start work on the task before submitting it for review."
    started = (await move(world, tid, "in_progress")).json()
    assert started["permissions"]["submit"] is True
    assert (await submit(world, tid, note="  ")).status_code == 422
    assert (await submit(world, tid, link="ftp://x")).status_code == 422

    sent = await submit(world, tid, link="https://docs.example.com/roadmap")
    assert sent.status_code == 201, sent.text
    detail = sent.json()
    assert detail["status"] == "internal_review"
    assert detail["versions"][0]["number"] == 1
    assert detail["versions"][0]["link"] == "https://docs.example.com/roadmap"
    request = detail["open_approval"]
    assert (request["stage"], request["version"]) == ("internal", 1)
    assert request["approver"]["id"] == str(pm.id)
    assert detail["permissions"]["decide"] is False
    assert detail["permissions"]["submit"] is False
    assert (
        detail["permissions"]["decide_blocked"]
        == "Only the task's reviewer can decide this review."
    )
    assert (await decide(world, request["id"], decision="approved")).status_code == 403
    assert (await world.http.get("/api/v1/approvals", params={"view": "mine"})).json() == []

    # The reviewer sees it waiting and requests changes (feedback required).
    await world.act_as(pm)
    mine = (await world.http.get("/api/v1/approvals", params={"view": "mine"})).json()
    assert [(a["task_code"], a["stage"], a["version"]) for a in mine] == [
        (task["code"], "internal", 1)
    ]
    review = (await world.http.get("/api/v1/tasks", params={"view": "review"})).json()
    assert [t["id"] for t in review] == [tid]
    bell = (await world.http.get("/api/v1/notifications")).json()["items"]
    assert bell[0]["title"] == "Awaiting your internal review: Technical fixes roadmap v1"
    assert (await world.http.get(f"/api/v1/tasks/{tid}")).json()["permissions"]["decide"] is True
    no_note = await decide(world, request["id"], decision="changes")
    assert error(no_note) == "Add feedback explaining the requested changes."
    back = (await decide(world, request["id"], decision="changes", note="Add the 404 list")).json()
    assert back["status"] == "in_progress"
    assert back["open_approval"] is None
    feedback = back["versions"][0]["feedback"]
    assert [(f["result"], f["by"], f["note"]) for f in feedback] == [
        ("changes", "Tomas", "Add the 404 list")
    ]
    again = await decide(world, request["id"], decision="approved")
    assert error(again) == "This request has already been decided."

    # v2 → approved internally → client stage, recorded by the client's AM.
    await world.act_as(dev)
    v2 = (await submit(world, tid, note="404 list added")).json()
    assert v2["versions"][1]["number"] == 2
    await world.act_as(pm)
    to_client = (await decide(world, v2["open_approval"]["id"], decision="approved")).json()
    assert to_client["status"] == "client_approval"
    client_request = to_client["open_approval"]
    assert (client_request["stage"], client_request["version"]) == ("client", 2)
    assert client_request["approver"]["id"] == str(am.id)
    assert client_request["requested_by"]["id"] == str(dev.id)
    assert (await decide(world, client_request["id"], decision="approved")).status_code == 403

    await world.act_as(am)
    assert to_client["client_contact"] == "Pat Buyer"
    who = await decide(world, client_request["id"], decision="approved", client_channel="call")
    assert error(who) == "Record who at the client made this decision."
    how = await decide(world, client_request["id"], decision="approved", client_decider="Pat")
    assert error(how) == "Record how the client communicated the decision."
    done = (
        await decide(
            world,
            client_request["id"],
            decision="approved",
            client_decider="Pat Buyer",
            client_channel="call",
        )
    ).json()
    assert done["status"] == "completed"
    assert done["completed_at"] is not None
    assert [(f["stage"], f["result"], f["by"]) for f in done["versions"][1]["feedback"]] == [
        ("internal", "approved", "Tomas"),
        ("client", "approved", "Pat Buyer (client, via a call)"),
    ]

    everything = (await world.http.get("/api/v1/approvals")).json()
    assert [(a["stage"], a["version"], a["status"]) for a in everything] == [
        ("client", 2, "approved"),
        ("internal", 2, "approved"),
        ("internal", 1, "changes"),
    ]
    activity = [
        a["summary"] for a in (await world.http.get(f"/api/v1/clients/{cid}/activity")).json()
    ]
    assert '"Technical fixes roadmap" v1 submitted for internal review' in activity
    assert 'Tomas requested changes to "Technical fixes roadmap" v1' in activity
    assert (
        'Pat Buyer (client, via a call) approved "Technical fixes roadmap" v2; task completed'
        in activity
    )
    one = (await world.http.get(f"/api/v1/approvals/{client_request['id']}")).json()
    assert (one["task_id"], one["status"]) == (tid, "approved")


async def test_no_self_review_and_reviewer_change(world: World) -> None:
    am = await world.user("anika@example.com", "account_manager")
    pm = await world.user("tomas@example.com", "project_manager")
    lead = await world.user("mei@example.com", "team_lead")
    _, task = await setup_task(world, am, pm, pm)  # the PM is assignee and reviewer
    tid = task["id"]
    await move(world, tid, "in_progress")
    own = await submit(world, tid)
    assert error(own) == "You can't review your own work. Ask the PM to set another reviewer."

    # Change the reviewer; an open internal review follows the new reviewer.
    changed = await world.http.patch(f"/api/v1/tasks/{tid}", json={"reviewer_id": str(lead.id)})
    assert changed.json()["reviewer"]["id"] == str(lead.id)
    sent = (await submit(world, tid)).json()
    assert sent["open_approval"]["approver"]["id"] == str(lead.id)
    reassigned = await world.http.patch(f"/api/v1/tasks/{tid}", json={"reviewer_id": str(am.id)})
    assert reassigned.json()["open_approval"]["approver"]["id"] == str(am.id)
    assert (
        await world.http.patch(f"/api/v1/tasks/{tid}", json={"reviewer_id": None})
    ).status_code == 422

    # Cancelling the task cancels the open request.
    cancelled = (await move(world, tid, "cancelled")).json()
    assert cancelled["open_approval"] is None
    statuses = (await world.http.get("/api/v1/approvals")).json()
    assert [a["status"] for a in statuses] == ["cancelled"]


async def test_client_only_task_and_self_approval(world: World) -> None:
    am = await world.user("anika@example.com", "account_manager")
    pm = await world.user("tomas@example.com", "project_manager")
    admin = await world.user("ravi@example.com", "super_admin")
    _, task = await setup_task(
        world, am, pm, am, requires_review=False, requires_client_approval=True
    )
    tid = task["id"]
    await world.act_as(am)
    await move(world, tid, "in_progress")
    sent = (await submit(world, tid)).json()
    assert sent["status"] == "client_approval"
    request = sent["open_approval"]
    assert request["stage"] == "client"
    assert (
        sent["permissions"]["decide_blocked"]
        == "You submitted this version, so you can't approve it."
    )
    refused = await decide(
        world, request["id"], decision="approved", client_decider="Pat", client_channel="email"
    )
    assert refused.status_code == 403

    # Super Admin may record it; "changes" sends the task back.
    await world.act_as(admin)
    back = (
        await decide(
            world,
            request["id"],
            decision="changes",
            note="Client wants a shorter intro",
            client_decider="Pat",
            client_channel="whatsapp",
        )
    ).json()
    assert back["status"] == "in_progress"
    assert back["versions"][0]["feedback"][0]["by"] == "Pat (client, via WhatsApp)"


async def test_rules_and_scope(world: World) -> None:
    am = await world.user("anika@example.com", "account_manager")
    pm = await world.user("tomas@example.com", "project_manager")
    dev = await world.user("jordan@example.com", "employee")
    outsider = await world.user("sam@example.com", "employee")
    _, plain = await setup_task(world, am, pm, dev, requires_review=False)
    await world.act_as(dev)
    await move(world, plain["id"], "in_progress")
    assert error(await submit(world, plain["id"])) == (
        "This task doesn't need review. Mark it completed instead."
    )

    await world.act_as(pm)
    reviewed = (
        await world.http.post(
            "/api/v1/tasks",
            json={"project_id": plain["project_id"], "title": "Audit", "assignee_id": str(dev.id)},
        )
    ).json()
    await world.act_as(dev)
    await move(world, reviewed["id"], "in_progress")
    request = (await submit(world, reviewed["id"])).json()["open_approval"]
    assert (
        error(await submit(world, reviewed["id"])) == "This task is already waiting for a decision."
    )
    assert (await move(world, reviewed["id"], "in_progress")).status_code == 422

    await world.act_as(outsider)
    assert (await world.http.get(f"/api/v1/approvals/{request['id']}")).status_code == 404
    assert (await world.http.get("/api/v1/approvals")).json() == []
    assert (await decide(world, request["id"], decision="approved")).status_code == 404
    assert (await submit(world, reviewed["id"])).status_code == 404

    count = await world.session.scalar(select(func.count()).select_from(Approval))
    assert count == 1
