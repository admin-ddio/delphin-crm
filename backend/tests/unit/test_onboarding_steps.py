"""The 13-step evaluation (pure)."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from app.modules.onboarding.steps import (
    DEFAULT_ACCESS_ITEMS,
    STEP_KEYS,
    AccessSnapshot,
    Snapshot,
    evaluate,
)

PROFILE: dict[str, Any] = {
    "website": "https://acme.com",
    "industry": "Retail",
    "contact_name": "Pat",
    "contact_email": "pat@acme.com",
}


def access(status: str) -> tuple[AccessSnapshot, ...]:
    return tuple(AccessSnapshot(label, status) for _, label in DEFAULT_ACCESS_ITEMS)


READY_FOR_REVIEW = Snapshot(
    **PROFILE,
    contract="signed",
    questionnaire="submitted",
    access=access("verified"),
    kpis_total=2,
    kpis_unconfirmed=0,
    kickoff_client="done",
    kickoff_internal="done",
    team_size=1,
)


def states(snap: Snapshot) -> dict[str, str]:
    return {step.key: step.state for step in evaluate(snap).steps}


def test_brand_new_client() -> None:
    result = evaluate(Snapshot())
    assert len(result.steps) == 13
    assert [s.number for s in result.steps] == list(range(1, 14))
    assert result.state("created") == "done"
    assert result.state("contract") == "todo"
    assert result.state("profile") == "progress"
    assert result.steps[2].detail == "Missing: website, industry, primary contact"
    assert result.progress == 8  # 1 of 13
    assert result.status == "in_progress"
    assert result.next_step is not None
    assert result.next_step.label == "Contract signed"
    assert result.state("project") == "todo"


def test_contract_and_questionnaire_progress() -> None:
    snap = Snapshot(**PROFILE, contract="draft", questionnaire="sent")
    result = evaluate(snap)
    assert result.state("contract") == "progress"
    assert result.steps[0].detail == "Recorded, not yet signed"
    assert result.state("profile") == "done"
    assert result.state("q_sent") == "done"
    assert result.state("q_done") == "progress"
    assert result.steps[4].detail == "Awaiting the client"


def test_access_states() -> None:
    assert states(Snapshot(access=access("pending")))["access_in"] == "todo"
    some_received = (AccessSnapshot("GSC", "received"), AccessSnapshot("GA4", "pending"))
    partial = evaluate(Snapshot(access=some_received))
    assert partial.state("access_in") == "progress"
    assert partial.steps[5].detail == "Outstanding: GA4"
    assert partial.state("access_ok") == "todo"

    all_received = states(Snapshot(access=access("received")))
    assert all_received["access_in"] == "done"
    assert all_received["access_ok"] == "todo"

    one_verified = (AccessSnapshot("GSC", "verified"), AccessSnapshot("GA4", "received"))
    assert states(Snapshot(access=one_verified))["access_ok"] == "progress"

    # Not-required items don't count.
    optional = (AccessSnapshot("GSC", "verified"), AccessSnapshot("GA4", "not_required"))
    assert states(Snapshot(access=optional))["access_ok"] == "done"


def test_rejected_access_blocks_onboarding() -> None:
    items = (AccessSnapshot("GSC", "rejected"), AccessSnapshot("GA4", "verified"))
    result = evaluate(Snapshot(access=items))
    assert result.blocked
    assert result.status == "blocked"
    assert result.state("access_in") == "blocked"
    assert result.steps[5].detail == "Rejected: GSC"
    assert result.state("access_ok") == "blocked"


def test_kpis_and_kickoffs() -> None:
    assert states(Snapshot())["kpi"] == "todo"
    pending = evaluate(Snapshot(kpis_total=2, kpis_unconfirmed=1))
    assert pending.state("kpi") == "progress"
    assert pending.steps[7].detail == "1 awaiting client confirmation"
    assert states(Snapshot(kpis_total=2))["kpi"] == "done"

    assert states(Snapshot(kickoff_client="scheduled"))["kickoff_client"] == "progress"
    no_team = evaluate(Snapshot(kickoff_internal="done"))
    assert no_team.state("kickoff_internal") == "progress"
    assert no_team.steps[9].detail == "No team assigned"
    team_only = evaluate(Snapshot(team_size=1))
    assert team_only.state("kickoff_internal") == "progress"
    assert team_only.steps[9].detail == "Internal kickoff not completed"
    assert states(Snapshot(kickoff_internal="done", team_size=2))["kickoff_internal"] == "done"


def test_review_and_completion_gates() -> None:
    almost = replace(READY_FOR_REVIEW, kickoff_client="scheduled")
    assert states(almost)["review"] == "todo"
    assert evaluate(almost).incomplete(STEP_KEYS[:10]) == ["Client kickoff meeting"]

    ready = evaluate(READY_FOR_REVIEW)
    assert ready.state("review") == "progress"
    assert ready.steps[10].detail == "Ready for review"
    assert ready.incomplete(STEP_KEYS[:10]) == []

    reviewed = evaluate(replace(READY_FOR_REVIEW, reviewed=True))
    assert reviewed.state("review") == "done"
    assert reviewed.state("done") == "progress"

    completed = evaluate(replace(READY_FOR_REVIEW, reviewed=True, completed=True))
    assert completed.status == "completed"
    assert completed.state("done") == "done"
    assert completed.state("project") == "progress"  # until the Projects module exists
    assert completed.progress == 92  # 12 of 13


def test_completion_freezes_earlier_steps() -> None:
    # Even if something later regresses, a completed onboarding shows steps 1–12 done.
    snap = Snapshot(completed=True)
    assert all(states(snap)[key] == "done" for key in STEP_KEYS[:12])
