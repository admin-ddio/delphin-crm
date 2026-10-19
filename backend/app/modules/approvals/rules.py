"""Who may decide an approval (pure; shared by the tasks and approvals services).

Demo rules (TODO(pilot-port): confirm against services/approvals.ts):
- internal stage: the task's reviewer decides;
- client stage: the client's Account Manager records the client's decision
  (`approvals.client_decision`);
- Super Admin may decide either stage;
- nobody approves their own submission (Super Admin excepted).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.authz.actor import Actor
from app.authz.permissions import APPROVALS_CLIENT_DECISION

CHANNEL_LABELS = {
    "email": "e-mail",
    "call": "a call",
    "meeting": "a meeting",
    "whatsapp": "WhatsApp",
}
STAGE_LABELS = {"internal": "internal review", "client": "client approval"}
SELF_APPROVAL = "You submitted this version, so you can't approve it."


@dataclass(frozen=True, slots=True)
class OpenRequest:
    stage: str
    approver_id: uuid.UUID | None
    requested_by_id: uuid.UUID | None
    client_manager_id: uuid.UUID


def designated_decider(request: OpenRequest) -> uuid.UUID | None:
    return request.approver_id if request.stage == "internal" else request.client_manager_id


def decision_block(actor: Actor, request: OpenRequest) -> str | None:
    """None if the actor may decide now, else the reason they can't."""
    if actor.is_super_admin:
        return None
    if actor.user_id != designated_decider(request):
        return (
            "Only the task's reviewer can decide this review."
            if request.stage == "internal"
            else "Only the client's Account Manager can record the client's decision."
        )
    if request.stage == "client" and not actor.can(APPROVALS_CLIENT_DECISION):
        return "You don't have permission to record client decisions."
    if request.requested_by_id == actor.user_id:
        return SELF_APPROVAL
    return None
