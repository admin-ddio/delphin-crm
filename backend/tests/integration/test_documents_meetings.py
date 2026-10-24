"""Client documents (private storage), meetings and the notification bell, end to end."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from tests.integration.test_onboarding import World, error, world

pytestmark = pytest.mark.integration

__all__ = ["world"]  # fixture re-export


async def upload(w: World, client_id: str, name: str, data: bytes, **form: str) -> Any:
    return await w.http.post(
        f"/api/v1/documents/clients/{client_id}",
        files={"file": (name, data, "application/octet-stream")},
        data=form,
    )


async def test_documents_upload_download_folders_and_rules(world: World) -> None:
    am = await world.user("anika@example.com", "account_manager")
    member = await world.user("jordan@example.com", "employee")
    outsider = await world.user("sam@example.com", "employee")
    await world.act_as(am)
    cid = await world.client(am)
    await world.post(cid, "team", {"user_id": str(member.id)})

    listing = (await world.http.get(f"/api/v1/documents/clients/{cid}")).json()
    assert [f["name"] for f in listing["folders"]] == [
        "Contracts",
        "SEO Files",
        "Brand Assets",
        "Reports",
        "Other",
    ]
    assert listing["permissions"] == {"upload": True, "manage_folders": True}

    contract = await upload(
        world, cid, "../../etc/Signed Contract.PDF", b"%PDF-1.7 test", folder="Contracts"
    )
    assert contract.status_code == 201, contract.text
    doc = contract.json()
    assert (doc["filename"], doc["content_type"], doc["size"]) == (
        "Signed Contract.PDF",
        "application/pdf",
        13,
    )
    download = await world.http.get(doc["download_url"])
    assert download.status_code == 200
    assert download.content == b"%PDF-1.7 test"
    assert download.headers["content-disposition"].startswith("attachment;")
    assert download.headers["x-content-type-options"] == "nosniff"

    bad_type = await upload(world, cid, "run.exe", b"MZ")
    assert error(bad_type).startswith("This file type isn't allowed.")
    empty = await upload(world, cid, "empty.txt", b"")
    assert error(empty) == "The file is empty."
    unknown_folder = await upload(world, cid, "a.txt", b"x", folder="Nope")
    assert error(unknown_folder) == "Choose one of this client's folders."

    detail = await world.detail(cid)
    assert (detail["documents"], detail["contract_documents"]) == (1, 1)
    assert next(q for q in detail["quick_status"] if q["key"] == "documents")["state"] == (
        "completed"
    )

    # Custom folders: create, rename, can't delete while used; defaults are fixed.
    created = await world.http.post(
        f"/api/v1/documents/clients/{cid}/folders", json={"name": "Audits"}
    )
    audits = next(f for f in created.json()["folders"] if f["name"] == "Audits")
    dupe = await world.http.post(
        f"/api/v1/documents/clients/{cid}/folders", json={"name": "audits"}
    )
    assert dupe.status_code == 409
    contracts = next(f for f in created.json()["folders"] if f["name"] == "Contracts")
    fixed = await world.http.delete(f"/api/v1/documents/folders/{contracts['id']}")
    assert error(fixed) == "Default folders can't be renamed or deleted."
    moved = await world.http.patch(
        f"/api/v1/documents/{doc['id']}", json={"folder_id": audits["id"]}
    )
    assert moved.json()["folder_id"] == audits["id"]
    busy = await world.http.delete(f"/api/v1/documents/folders/{audits['id']}")
    assert error(busy) == "Move or delete the folder's documents first."

    # Team members upload but can't delete others' files; outsiders see nothing.
    await world.act_as(member)
    mine = (await upload(world, cid, "keywords.csv", b"kw,vol\n", folder="SEO Files")).json()
    assert mine["can_delete"] is True
    assert (await world.http.delete(f"/api/v1/documents/{doc['id']}")).status_code == 403
    await world.act_as(outsider)
    assert (await world.http.get(f"/api/v1/documents/clients/{cid}")).status_code == 404
    assert (await world.http.get(doc["download_url"])).status_code == 404

    await world.act_as(am)
    assert (await world.http.delete(f"/api/v1/documents/{mine['id']}")).status_code == 204
    activity = [
        a["summary"] for a in (await world.http.get(f"/api/v1/clients/{cid}/activity")).json()
    ]
    assert "Document uploaded: Signed Contract.PDF (Contracts)" in activity
    assert "Document deleted: keywords.csv" in activity


async def test_meetings_lifecycle_and_action_items(world: World) -> None:
    am = await world.user("anika@example.com", "account_manager")
    pm = await world.user("tomas@example.com", "project_manager")
    outsider = await world.user("sam@example.com", "employee")
    await world.act_as(am)
    cid = await world.client(am)
    start = datetime.now(UTC) + timedelta(days=2)
    body = {
        "client_id": cid,
        "title": "Access Review Meeting",
        "description": "Review and verify all access details",
        "type": "review",
        "starts_at": start.isoformat(),
        "ends_at": (start + timedelta(minutes=45)).isoformat(),
        "platform": "zoom",
        "location": "https://zoom.example/j/1",
        "attendee_ids": [str(pm.id)],
        "guests": [{"name": "John Doe", "email": "john@acme.com"}],
    }
    backwards = await world.http.post(
        "/api/v1/meetings", json={**body, "ends_at": start.isoformat()}
    )
    assert backwards.status_code == 422
    created = (await world.http.post("/api/v1/meetings", json=body)).json()
    assert created["display_status"] == "upcoming"
    assert [(a["name"], a["external"]) for a in created["attendees"]] == [
        ("Tomas", False),
        ("John Doe", True),
    ]
    future = await world.http.post(
        f"/api/v1/meetings/{created['id']}/complete", json={"notes": "Done"}
    )
    assert error(future) == "This meeting hasn't started yet."

    later = start + timedelta(days=1)
    moved = await world.http.patch(
        f"/api/v1/meetings/{created['id']}",
        json={"starts_at": later.isoformat(), "ends_at": (later + timedelta(hours=1)).isoformat()},
    )
    assert moved.status_code == 200, moved.text
    item = await world.http.post(
        f"/api/v1/meetings/{created['id']}/action-items",
        json={"title": "Share CMS login via vault", "owner_id": str(pm.id)},
    )
    item_id = item.json()["action_items"][0]["id"]

    # The owner may tick off their own action item.
    await world.act_as(pm)
    ticked = await world.http.patch(f"/api/v1/meetings/action-items/{item_id}", json={"done": True})
    assert ticked.json()["action_items"][0]["done"] is True
    titles = [n["title"] for n in (await world.http.get("/api/v1/notifications")).json()["items"]]
    assert "Meeting scheduled: Access Review Meeting" in titles
    assert "Meeting moved: Access Review Meeting" in titles
    assert "Action item for Acme Ltd: Share CMS login via vault" in titles

    await world.act_as(am)
    cancelled = await world.http.post(
        f"/api/v1/meetings/{created['id']}/cancel", json={"reason": "Client travelling"}
    )
    assert cancelled.json()["status"] == "cancelled"
    again = await world.http.patch(f"/api/v1/meetings/{created['id']}", json={"title": "x"})
    assert error(again) == "This meeting is already cancelled."
    listing = (await world.http.get(f"/api/v1/meetings/clients/{cid}")).json()
    assert listing["stats"] == {"total": 1, "completed": 0, "upcoming": 0, "cancelled": 1}

    await world.act_as(outsider)
    assert (await world.http.get(f"/api/v1/meetings/clients/{cid}")).status_code == 404
    assert (await world.http.post("/api/v1/meetings", json=body)).status_code == 404


async def test_notification_bell(world: World) -> None:
    am = await world.user("anika@example.com", "account_manager")
    admin = await world.user("ravi@example.com", "super_admin")
    await world.act_as(admin)
    await world.client(am)  # created by someone else → the AM is told
    await world.act_as(am)
    bell = (await world.http.get("/api/v1/notifications")).json()
    assert bell["unread"] == 1
    first = bell["items"][0]
    assert first["title"] == "You're the Account Manager for Acme Ltd"
    assert first["link"].startswith("/clients/")
    read = (await world.http.post(f"/api/v1/notifications/{first['id']}/read")).json()
    assert (read["unread"], read["items"][0]["read"]) == (0, True)
    await world.act_as(admin)
    assert (await world.http.get("/api/v1/notifications")).json()["unread"] == 0
    other = await world.http.post(f"/api/v1/notifications/{first['id']}/read")
    assert other.status_code == 404
    await world.act_as(am)
    assert (await world.http.post("/api/v1/notifications/read-all")).json()["unread"] == 0
