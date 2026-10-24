"""The 13-step evaluation, stages, next actions, questionnaire and KPI rules (pure)."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal
from typing import Any

from app.modules.onboarding import kpis
from app.modules.onboarding import questionnaire as q
from app.modules.onboarding.steps import (
    DEFAULT_ACCESS_ITEMS,
    STEP_KEYS,
    AccessSnapshot,
    Snapshot,
    evaluate,
)

PROFILE: dict[str, Any] = {
    "contract_captured": True,
    "website": "https://acme.com",
    "industry": "Retail",
    "contact_name": "Pat",
    "contact_email": "pat@acme.com",
    "contact_phone": "+91 98765 43210",
}


def access(status: str) -> tuple[AccessSnapshot, ...]:
    return tuple(AccessSnapshot(label, status) for _, label, _ in DEFAULT_ACCESS_ITEMS)


READY_FOR_REVIEW = Snapshot(
    **PROFILE,
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
    assert result.steps[0].detail == "No contract dates"
    assert result.state("profile") == "progress"
    assert result.steps[2].detail == "Missing: website, industry, primary contact"
    assert result.progress == 8  # 1 of 13
    assert result.status == "in_progress"
    assert result.next_step is not None
    assert result.next_step.label == "Contract signed"


def test_created_with_contract_and_profile() -> None:
    result = evaluate(Snapshot(**PROFILE, questionnaire="sent"))
    assert [result.state(k) for k in ("contract", "created", "profile", "q_sent")] == ["done"] * 4
    assert result.state("q_done") == "progress"
    assert result.steps[4].detail == "Awaiting the client"
    no_phone = evaluate(Snapshot(**{**PROFILE, "contact_phone": None}))
    assert no_phone.steps[2].detail == "Missing: primary contact"


def test_access_states() -> None:
    assert states(Snapshot(access=access("pending")))["access_in"] == "todo"
    some = (AccessSnapshot("GSC", "received"), AccessSnapshot("GA4", "requested"))
    partial = evaluate(Snapshot(access=some))
    assert partial.state("access_in") == "progress"
    assert partial.steps[5].detail == "Outstanding: GA4"
    assert partial.state("access_ok") == "todo"
    one_verified = (AccessSnapshot("GSC", "verified"), AccessSnapshot("GA4", "received"))
    assert states(Snapshot(access=one_verified))["access_ok"] == "progress"
    optional = (AccessSnapshot("GSC", "verified"), AccessSnapshot("GA4", "not_required"))
    assert states(Snapshot(access=optional))["access_ok"] == "done"


def test_rejected_access_blocks_onboarding() -> None:
    items = (AccessSnapshot("GSC", "rejected"), AccessSnapshot("GA4", "verified"))
    result = evaluate(Snapshot(access=items))
    assert (result.blocked, result.status) == (True, "blocked")
    assert result.state("access_in") == "blocked"
    assert result.steps[5].detail == "Rejected: GSC"
    access_stage = next(s for s in result.stages if s.key == "access")
    assert access_stage.state == "blocked"


def test_kpis_and_kickoff_meetings() -> None:
    assert states(Snapshot())["kpi"] == "todo"
    pending = evaluate(Snapshot(kpis_total=2, kpis_unconfirmed=1))
    assert pending.steps[7].detail == "1 awaiting client confirmation"
    assert states(Snapshot(kpis_total=2))["kpi"] == "done"

    scheduled = evaluate(Snapshot(kickoff_client="scheduled"))
    assert scheduled.state("kickoff_client") == "progress"
    assert scheduled.steps[8].detail == "Kickoff call scheduled, notes not recorded"
    assert evaluate(Snapshot()).steps[8].detail == "No kickoff call scheduled"
    no_team = evaluate(Snapshot(kickoff_internal="done"))
    assert (no_team.state("kickoff_internal"), no_team.steps[9].detail) == (
        "progress",
        "No team assigned",
    )
    team_only = evaluate(Snapshot(team_size=1))
    assert team_only.steps[9].detail == "No internal kickoff scheduled"
    assert states(Snapshot(kickoff_internal="done", team_size=2))["kickoff_internal"] == "done"


def test_review_completion_and_stages() -> None:
    almost = replace(READY_FOR_REVIEW, kickoff_client="scheduled")
    assert evaluate(almost).incomplete(STEP_KEYS[:10]) == ["Client kickoff meeting"]
    ready = evaluate(READY_FOR_REVIEW)
    assert (ready.state("review"), ready.steps[10].detail) == ("progress", "Ready for review")
    assert [s.state for s in ready.stages] == [
        "completed",
        "completed",
        "completed",
        "completed",
        "completed",
        "in_progress",
    ]
    completed = evaluate(replace(READY_FOR_REVIEW, reviewed=True, completed=True))
    assert completed.status == "completed"
    assert completed.state("project") == "progress"
    assert completed.progress == 92  # 12 of 13
    assert evaluate(replace(READY_FOR_REVIEW, completed=True, has_project=True)).progress == 100
    stages = evaluate(Snapshot(**PROFILE)).stages
    assert [(s.label, s.state) for s in stages[:2]] == [
        ("Client Created", "completed"),
        ("Questionnaire", "pending"),
    ]


def test_completion_freezes_earlier_steps() -> None:
    snap = Snapshot(completed=True)
    assert all(states(snap)[key] == "done" for key in STEP_KEYS[:12])


def test_next_actions_are_dated_and_prioritised() -> None:
    created = date(2026, 5, 1)
    actions = evaluate(Snapshot(**PROFILE)).next_actions(created, today=date(2026, 5, 2))
    assert [a.step for a in actions] == ["q_sent", "q_done", "access_in", "access_ok"]
    assert [a.due for a in actions] == [
        date(2026, 5, 3),
        date(2026, 5, 6),
        date(2026, 5, 6),
        date(2026, 5, 8),
    ]
    assert [a.priority for a in actions] == ["high", "medium", "medium", "low"]
    late = evaluate(Snapshot(**PROFILE)).next_actions(created, today=date(2026, 5, 20), limit=1)
    assert (late[0].title, late[0].priority) == ("Send the onboarding questionnaire", "high")


def test_questionnaire_completeness() -> None:
    assert q.missing({}) == [
        "Business Goals: at least one goal",
        "Business Goals: your goals in detail",
        "Target Markets: target locations",
        "Target Markets: target audiences",
        "Competitors: at least one competitor",
        "Brand Voice: at least one tone",
        "Past SEO Work: whether SEO was done before",
    ]
    full = {
        "business_goals": {"goals": ["leads", "other"], "other": "", "details": "More leads"},
        "target_markets": {"locations": "India", "audiences": "CFOs"},
        "competitors": {"competitors": [{"name": "WidgetCo"}]},
        "brand_voice": {"tones": ["professional"]},
        "past_seo": {"worked_before": "no"},
    }
    assert q.missing(full) == ["Business Goals: the other goal"]
    full["business_goals"]["other"] = "Win awards"  # type: ignore[index]
    assert q.missing(full) == []
    assert q.missing_by_section(full)["additional"] == []


def test_questionnaire_legacy_answers_are_mapped() -> None:
    legacy = {"business_goals": "Grow", "target_markets": "US", "brand_voice": "Calm"}
    mapped = q.from_legacy(legacy)
    assert mapped["business_goals"] == {"goals": [], "details": "Grow"}
    assert mapped["target_markets"]["locations"] == "US"
    assert mapped["brand_voice"]["guidelines"] == "Calm"
    assert q.from_legacy(mapped) is mapped


def test_kpi_progress_and_status() -> None:
    d = Decimal
    assert kpis.progress(d(10000), d(14000), None) is None
    assert kpis.progress(d(10000), d(14000), d(11200)) == 30
    assert kpis.progress(d(10000), d(14000), d(20000)) == 100
    assert kpis.progress(d(10), d(5), d(7)) == 60  # lower is better
    assert kpis.progress(d(5), d(5), d(5)) == 100
    start, end = date(2026, 1, 1), date(2027, 1, 1)
    halfway = date(2026, 7, 2)
    assert kpis.status(None, start, end, halfway) == "not_measured"
    assert kpis.status(100, start, end, halfway) == "achieved"
    assert kpis.status(48, start, end, halfway) == "on_track"
    assert kpis.status(35, start, end, halfway) == "at_risk"
    assert kpis.status(20, start, end, halfway) == "behind"
    assert kpis.status(1, start, None, halfway) == "on_track"  # no deadline
