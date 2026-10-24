"""Projects and tasks API end to end on PostgreSQL: creation gate, template, board moves, scope."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import select

from app.modules.clients.models import ClientTeamMember
from app.modules.onboarding.models import ClientOnboarding
from app.platform.audit.models import AuditLog
from app.platform.identity.models import User
from tests.integration.test_onboarding import World, error, step, world

pytestmark = pytest.mark.integration

__all__ = ["world"]  # fixture re-export

START = date(2026, 3, 2)


async def complete_onboarding(w: World, client_id: str) -> None:
    w.session.add(ClientOnboarding(client_id=uuid.UUID(client_id), completed_at=datetime.now(UTC)))
    await w.session.flush()


async def add_to_team(w: World, client_id: str, user: User, *, ago: int = 0) -> None:
    w.session.add(
        ClientTeamMember(
            client_id=uuid.UUID(client_id),
            user_id=user.id,
            added_at=datetime.now(UTC) - timedelta(minutes=ago),
        )
    )
    await w.session.flush()


async def new_project(w: World, client_id: str, manager: User, **fields: Any) -> httpx.Response:
    body = {
        "client_id": client_id,
        "name": "SEO foundation",
        "manager_id": str(manager.id),
        "start_date": START.isoformat(),
        **fields,
    }
    return await w.http.post("/api/v1/projects", json=body)


async def move(w: World, task_id: str, status: str) -> httpx.Response:
    return await w.http.post(f"/api/v1/tasks/{task_id}/status", json={"status": status})


async def test_project_creation_requires_completed_onboarding(world: World) -> None:
    am = await world.user("anika@example.com", "account_manager")
    pm = await world.user("tomas@example.com", "project_manager")
    await world.act_as(am)
    cid = await world.client(am)

    blocked = await new_project(world, cid, pm)
    assert blocked.status_code == 422
    assert error(blocked) == "Projects can only be created after client onboarding is completed."
    assert (await world.http.get("/api/v1/projects/eligible-clients")).json() == []

    await complete_onboarding(world, cid)
    eligible = (await world.http.get("/api/v1/projects/eligible-clients")).json()
    assert [(c["id"], c["has_project"]) for c in eligible] == [(cid, False)]
    assert step(await world.detail(cid), "project") == "progress"

    # The manager must be a Project Manager (or Super Admin).
    wrong = await new_project(world, cid, am)
    assert wrong.status_code == 422
    assert "Project Manager" in error(wrong)
    options = (await world.http.get("/api/v1/projects/manager-options")).json()
    assert [o["id"] for o in options] == [str(pm.id)]

    created = await new_project(world, cid, pm, template="blank")
    assert created.status_code == 201, created.text
    project = created.json()
    assert project["code"] == "PRJ-0001"
    assert project["tasks"] == []
    assert project["stats"] == {"tasks": 0, "open": 0, "overdue": 0, "in_review": 0, "progress": 0}
    assert project["template"] is None

    # Step 13 completes; the client now shows it has a project.
    assert step(await world.detail(cid), "project") == "done"
    board = (await world.http.get("/api/v1/onboarding")).json()
    assert board[0]["progress"] == 100
    eligible = (await world.http.get("/api/v1/projects/eligible-clients")).json()
    assert eligible[0]["has_project"] is True

    second = await new_project(world, cid, pm, name="Content sprint", template="blank")
    assert second.json()["code"] == "PRJ-0002"
    listed = (await world.http.get("/api/v1/projects", params={"client_id": cid})).json()
    assert [p["code"] for p in listed] == ["PRJ-0002", "PRJ-0001"]

    audit = (
        await world.session.execute(select(AuditLog).where(AuditLog.action == "project.created"))
    ).scalars()
    assert len(list(audit)) == 2
    activity = (await world.http.get(f"/api/v1/clients/{cid}/activity")).json()
    summaries = [a["summary"] for a in activity]
    assert "Project PRJ-0001 created: SEO foundation" in summaries
    assert "Onboarding step 13 done: first project created" in summaries


async def test_template_creates_dated_tasks_for_the_team(world: World) -> None:
    am = await world.user("anika@example.com", "account_manager")
    pm = await world.user("tomas@example.com", "project_manager")
    lead = await world.user("lee@example.com", "team_lead")
    first = await world.user("jordan@example.com", "employee")
    later = await world.user("sam@example.com", "employee")
    await world.act_as(am)
    cid = await world.client(am)
    await complete_onboarding(world, cid)
    await add_to_team(world, cid, lead, ago=30)  # not an employee: skipped
    await add_to_team(world, cid, first, ago=20)
    await add_to_team(world, cid, later, ago=10)

    project = (await new_project(world, cid, pm)).json()
    assert project["template"] == "seo_foundation"
    tasks = project["tasks"]
    assert [(t["code"], t["title"], t["due_date"]) for t in tasks] == [
        ("T-1", "Baseline SEO audit", "2026-03-07"),
        ("T-2", "Keyword research", "2026-03-09"),
        ("T-3", "Technical fixes roadmap", "2026-03-12"),
        ("T-4", "On-page optimisation of priority pages", "2026-03-28"),
        ("T-5", "Month 1 performance report", "2026-04-01"),
    ]
    assert {t["status"] for t in tasks} == {"backlog"}
    assert {t["assignee"]["id"] for t in tasks} == {str(first.id)}
    assert all(t["requires_review"] for t in tasks)
    assert [t["requires_client_approval"] for t in tasks] == [False, False, True, False, True]
    # START is in the past, so every open template task is overdue.
    assert all(t["overdue"] for t in tasks)
    assert project["stats"] == {"tasks": 5, "open": 5, "overdue": 5, "in_review": 0, "progress": 0}

    detail = (await world.http.get(f"/api/v1/tasks/{tasks[0]['id']}")).json()
    assert detail["reviewer"]["id"] == str(pm.id)


async def test_task_board_moves_and_rules(world: World) -> None:
    am = await world.user("anika@example.com", "account_manager")
    pm = await world.user("tomas@example.com", "project_manager")
    dev = await world.user("jordan@example.com", "employee")
    other = await world.user("sam@example.com", "employee")
    await world.act_as(am)
    cid = await world.client(am)
    await complete_onboarding(world, cid)
    await world.act_as(pm)
    project = (await new_project(world, cid, pm, template="blank")).json()

    created = await world.http.post(
        "/api/v1/tasks",
        json={
            "project_id": project["id"],
            "title": "  Fix redirects  ",
            "assignee_id": str(dev.id),
            "due_date": (datetime.now(UTC).date() + timedelta(days=3)).isoformat(),
            "requires_review": False,
        },
    )
    assert created.status_code == 201, created.text
    task = created.json()
    tid = task["id"]
    assert (task["title"], task["status"], task["overdue"]) == ("Fix redirects", "ready", False)
    assert task["permissions"]["manage"] is True
    assert task["permissions"]["next_statuses"] == ["backlog", "in_progress", "cancelled"]

    # The assignee works the task but can't cancel it.
    await world.act_as(dev)
    mine = (await world.http.get("/api/v1/tasks")).json()
    assert [t["id"] for t in mine] == [tid]
    me = (await world.http.get(f"/api/v1/tasks/{tid}")).json()["permissions"]
    assert me["work"] is True
    assert me["manage"] is False
    assert me["next_statuses"] == ["backlog", "in_progress"]
    cancel = await move(world, tid, "cancelled")
    assert cancel.status_code == 403
    assert (await move(world, tid, "in_progress")).json()["status"] == "in_progress"
    bad = await move(world, tid, "backlog")
    assert bad.status_code == 422
    assert error(bad) == "A task can't move from In progress to Backlog."
    assert (await move(world, tid, "blocked")).status_code == 200
    assert (await move(world, tid, "in_progress")).status_code == 200
    done = (await move(world, tid, "completed")).json()
    assert (done["status"], done["completed_at"] is not None) == ("completed", True)
    assert done["permissions"]["next_statuses"] == []
    assert (await world.http.get("/api/v1/tasks")).json() == []  # open only by default
    closed = (await world.http.get("/api/v1/tasks", params={"open_only": "false"})).json()
    assert [t["status"] for t in closed] == ["completed"]
    assert (await world.http.patch(f"/api/v1/tasks/{tid}", json={"title": "x"})).status_code == 403

    # Someone outside the project doesn't see it at all.
    await world.act_as(other)
    assert (await world.http.get(f"/api/v1/tasks/{tid}")).status_code == 404
    assert (await world.http.get(f"/api/v1/projects/{project['id']}")).status_code == 404
    assert (await world.http.get("/api/v1/projects")).json() == []
    assert (await move(world, tid, "in_progress")).status_code == 404

    # Review-required tasks can't be completed directly.
    await world.act_as(pm)
    reviewed = (
        await world.http.post(
            "/api/v1/tasks",
            json={"project_id": project["id"], "title": "Write audit", "assignee_id": str(dev.id)},
        )
    ).json()
    assert reviewed["requires_review"] is True
    await move(world, reviewed["id"], "in_progress")
    refused = await move(world, reviewed["id"], "completed")
    assert refused.status_code == 422
    assert error(refused) == (
        "This task requires review. Submit it for review instead of completing it directly."
    )

    # Manager edits: reassign, reschedule into the past → overdue; cancel and reopen.
    yesterday = (datetime.now(UTC).date() - timedelta(days=1)).isoformat()
    edited = await world.http.patch(
        f"/api/v1/tasks/{reviewed['id']}",
        json={"assignee_id": str(other.id), "due_date": yesterday},
    )
    assert edited.status_code == 200, edited.text
    assert (edited.json()["assignee"]["id"], edited.json()["overdue"]) == (str(other.id), True)
    assert (await move(world, reviewed["id"], "cancelled")).json()["overdue"] is False
    assert (await move(world, reviewed["id"], "backlog")).json()["status"] == "backlog"
    unknown = await world.http.patch(
        f"/api/v1/tasks/{reviewed['id']}", json={"assignee_id": str(uuid.uuid4())}
    )
    assert unknown.status_code == 422

    stats = (await world.http.get(f"/api/v1/projects/{project['id']}")).json()["stats"]
    assert stats == {"tasks": 2, "open": 1, "overdue": 1, "in_review": 0, "progress": 50}

    # Assigning a task makes the project visible to the assignee.
    await world.act_as(other)
    assert [p["id"] for p in (await world.http.get("/api/v1/projects")).json()] == [project["id"]]
    await world.act_as(pm)
    activity = (await world.http.get(f"/api/v1/clients/{cid}/activity")).json()
    assert any(a["summary"].startswith("Task T-1 moved to Completed") for a in activity)


async def test_permissions_on_create(world: World) -> None:
    am = await world.user("anika@example.com", "account_manager")
    pm = await world.user("tomas@example.com", "project_manager")
    dev = await world.user("jordan@example.com", "employee")
    await world.act_as(am)
    cid = await world.client(am)
    await complete_onboarding(world, cid)
    project = (await new_project(world, cid, pm, template="blank")).json()

    await world.act_as(dev)
    assert (await new_project(world, cid, pm)).status_code == 403
    denied = await world.http.post(
        "/api/v1/tasks", json={"project_id": project["id"], "title": "Sneaky"}
    )
    assert denied.status_code == 403

    await world.act_as(pm)
    missing = await world.http.post(
        "/api/v1/tasks", json={"project_id": str(uuid.uuid4()), "title": "Nowhere"}
    )
    assert missing.status_code == 404
    unassigned = (
        await world.http.post("/api/v1/tasks", json={"project_id": project["id"], "title": "Later"})
    ).json()
    assert (unassigned["status"], unassigned["assignee"]) == ("backlog", None)
    options = (await world.http.get("/api/v1/tasks/assignee-options")).json()
    assert {o["id"] for o in options} == {str(am.id), str(pm.id), str(dev.id)}
    assert (await world.http.get(f"/api/v1/projects/{uuid.uuid4()}")).status_code == 404


async def test_client_approval_tasks_cannot_be_completed_directly(world: World) -> None:
    am = await world.user("anika@example.com", "account_manager")
    pm = await world.user("tomas@example.com", "project_manager")
    await world.act_as(am)
    cid = await world.client(am)
    await complete_onboarding(world, cid)
    await world.act_as(pm)
    project = (await new_project(world, cid, pm, template="blank")).json()
    task = (
        await world.http.post(
            "/api/v1/tasks",
            json={
                "project_id": project["id"],
                "title": "Publish landing page",
                "assignee_id": str(pm.id),
                "requires_review": False,
                "requires_client_approval": True,
            },
        )
    ).json()
    started = (await move(world, task["id"], "in_progress")).json()
    assert "completed" not in started["permissions"]["next_statuses"]
    refused = await move(world, task["id"], "completed")
    assert refused.status_code == 422
    assert "requires review" in error(refused)
