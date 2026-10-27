"""The 13 onboarding steps, the 6 dashboard stages and the next actions, computed from
a snapshot. Pure: no database, no I/O.

Workflow (product owner's spec, 2026-10-19): 1 contract signed (captured on Create
Client) · 2 client created · 3 profile completed · 4 questionnaire sent · 5 submitted ·
6 access collected · 7 access verified · 8 KPI targets confirmed · 9 client kickoff
meeting · 10 internal team kickoff · 11 review · 12 completed · 13 project.
Progress = steps done ÷ 13; blocked when a required access item is rejected.
TODO(pilot-port): diff against services/onboarding.ts and docs/onboarding-workflow.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Final, Literal

StepState = Literal["todo", "progress", "done", "blocked"]
StageState = Literal["pending", "in_progress", "completed", "blocked"]
OverallStatus = Literal["in_progress", "blocked", "completed"]
Priority = Literal["high", "medium", "low"]

STEP_DEFS: Final[tuple[tuple[str, str, str], ...]] = (
    ("contract", "Contract signed", "Enter the contract dates on the client profile."),
    ("created", "Client created", ""),
    (
        "profile",
        "Client profile completed",
        "Add the website, industry and the primary contact's e-mail and phone.",
    ),
    ("q_sent", "Onboarding questionnaire sent", "Send the questionnaire link to the client."),
    ("q_done", "Questionnaire submitted", "The client submits it, or record their answers."),
    ("access_in", "Platform access collected", "Mark each platform as received."),
    ("access_ok", "Access verified", "An authorised team member verifies every item."),
    (
        "kpi",
        "KPI targets defined & confirmed",
        "Add KPI targets and record the client's confirmation.",
    ),
    ("kickoff_client", "Client kickoff meeting", "Schedule the kickoff call and record its notes."),
    (
        "kickoff_internal",
        "Internal team kickoff",
        "Assign the team and complete an internal kickoff meeting.",
    ),
    ("review", "Onboarding review", "Pass the review once steps 1–10 are done."),
    ("done", "Onboarding completed", "Complete onboarding."),
    ("project", "Delivery started", "Start a service (or create the delivery project)."),
)
STEP_KEYS: Final = tuple(key for key, _, _ in STEP_DEFS)
#: Steps 1–10 must be done before the review can pass.
PRE_REVIEW: Final = STEP_KEYS[:10]

#: The dashboard's progress tracker (mockup): six stages over the 13 steps.
STAGE_DEFS: Final[tuple[tuple[str, str, tuple[str, ...]], ...]] = (
    ("client", "Client Created", ("contract", "created", "profile")),
    ("questionnaire", "Questionnaire", ("q_sent", "q_done")),
    ("access", "Access", ("access_in", "access_ok")),
    ("kpis", "KPIs", ("kpi",)),
    ("kickoff", "Kickoff", ("kickoff_client", "kickoff_internal")),
    ("review", "Review", ("review", "done")),
)

#: Default target day (after the client is created) for each step: drives the
#: "Next steps" due dates and priorities. TODO(confirm): agency SLA.
TARGET_DAYS: Final[dict[str, int]] = {
    "contract": 0,
    "created": 0,
    "profile": 1,
    "q_sent": 2,
    "q_done": 5,
    "access_in": 5,
    "access_ok": 7,
    "kpi": 8,
    "kickoff_client": 9,
    "kickoff_internal": 10,
    "review": 12,
    "done": 14,
    "project": 15,
}
ACTIONS: Final[dict[str, str]] = {
    "contract": "Add contract details",
    "created": "Create the client",
    "profile": "Complete the client profile",
    "q_sent": "Send the onboarding questionnaire",
    "q_done": "Collect the questionnaire answers",
    "access_in": "Collect platform access",
    "access_ok": "Verify platform access",
    "kpi": "Define and confirm KPI targets",
    "kickoff_client": "Conduct the kickoff call",
    "kickoff_internal": "Internal team kickoff",
    "review": "Pass the onboarding review",
    "done": "Complete onboarding",
    "project": "Start delivery (a service or project)",
}

DEFAULT_ACCESS_ITEMS: Final = (
    ("GSC", "Google Search Console", "Access to GSC for domain performance data"),
    ("GA4", "Google Analytics 4", "GA4 access for traffic and conversion tracking"),
    ("CMS", "CMS Access", "Admin/editor access to the website CMS"),
    ("AHREFS", "Ahrefs Account", "Access to Ahrefs for SEO analysis"),
    ("GDRIVE", "Google Drive Access", "Shared drive for documents and reports"),
)


@dataclass(frozen=True, slots=True)
class AccessSnapshot:
    label: str
    status: str


@dataclass(frozen=True, slots=True)
class Snapshot:
    contract_captured: bool = False
    website: str | None = None
    industry: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    questionnaire: str = "none"
    access: tuple[AccessSnapshot, ...] = field(
        default_factory=lambda: tuple(
            AccessSnapshot(label, "pending") for _, label, _ in DEFAULT_ACCESS_ITEMS
        )
    )
    kpis_total: int = 0
    kpis_unconfirmed: int = 0
    #: From meetings: none | scheduled | done.
    kickoff_client: str = "none"
    kickoff_internal: str = "none"
    team_size: int = 0
    reviewed: bool = False
    completed: bool = False
    has_project: bool = False


@dataclass(frozen=True, slots=True)
class Step:
    number: int
    key: str
    label: str
    hint: str
    state: StepState
    detail: str


@dataclass(frozen=True, slots=True)
class Stage:
    key: str
    label: str
    state: StageState


@dataclass(frozen=True, slots=True)
class NextAction:
    step: str
    title: str
    detail: str
    due: date
    priority: Priority


@dataclass(frozen=True, slots=True)
class Evaluation:
    steps: tuple[Step, ...]
    progress: int
    blocked: bool
    status: OverallStatus

    def state(self, key: str) -> StepState:
        return next(step.state for step in self.steps if step.key == key)

    def incomplete(self, keys: tuple[str, ...]) -> list[str]:
        return [s.label for s in self.steps if s.key in keys and s.state != "done"]

    @property
    def next_step(self) -> Step | None:
        return next((s for s in self.steps if s.state != "done"), None)

    @property
    def stages(self) -> tuple[Stage, ...]:
        by_key = {s.key: s.state for s in self.steps}
        out = []
        for key, label, steps in STAGE_DEFS:
            states = [by_key[k] for k in steps]
            if all(s == "done" for s in states):
                state: StageState = "completed"
            elif "blocked" in states:
                state = "blocked"
            elif any(s in ("done", "progress") for s in states):
                state = "in_progress"
            else:
                state = "pending"
            out.append(Stage(key=key, label=label, state=state))
        return tuple(out)

    def next_actions(self, created: date, today: date, limit: int = 4) -> list[NextAction]:
        actions = []
        for step in self.steps:
            if step.state == "done" or step.key == "created":
                continue
            due = created + timedelta(days=TARGET_DAYS[step.key])
            days_left = (due - today).days
            priority: Priority = (
                "high"
                if step.state == "blocked" or days_left <= 2
                else "medium"
                if days_left <= 5
                else "low"
            )
            actions.append(
                NextAction(
                    step=step.key,
                    title=ACTIONS[step.key],
                    detail=step.detail or step.hint,
                    due=due,
                    priority=priority,
                )
            )
            if len(actions) == limit:
                break
        return actions


def _join(names: list[str]) -> str:
    return ", ".join(names)


def _meeting_step(state: str, what: str) -> tuple[StepState, str]:
    if state == "done":
        return "done", ""
    if state == "scheduled":
        return "progress", f"{what} scheduled, notes not recorded"
    return "todo", f"No {what.lower()} scheduled"


def evaluate(snap: Snapshot) -> Evaluation:  # noqa: PLR0912, PLR0915  # one branch per step
    out: dict[str, tuple[StepState, str]] = {}

    out["contract"] = ("done", "") if snap.contract_captured else ("todo", "No contract dates")
    out["created"] = ("done", "")

    missing = [
        name
        for name, ok in (
            ("website", bool(snap.website)),
            ("industry", bool(snap.industry)),
            (
                "primary contact",
                bool(snap.contact_name and snap.contact_email and snap.contact_phone),
            ),
        )
        if not ok
    ]
    out["profile"] = ("progress", f"Missing: {_join(missing)}") if missing else ("done", "")

    out["q_sent"] = ("todo", "Not sent") if snap.questionnaire == "none" else ("done", "")
    if snap.questionnaire == "submitted":
        out["q_done"] = ("done", "")
    elif snap.questionnaire == "sent":
        out["q_done"] = ("progress", "Awaiting the client")
    else:
        out["q_done"] = ("todo", "")

    required = [a for a in snap.access if a.status != "not_required"]
    rejected = [a.label for a in required if a.status == "rejected"]
    not_in = [a.label for a in required if a.status not in ("received", "verified")]
    not_ok = [a.label for a in required if a.status != "verified"]
    if rejected:
        out["access_in"] = ("blocked", f"Rejected: {_join(rejected)}")
        out["access_ok"] = ("blocked", f"Not verified: {_join(not_ok)}")
    else:
        if not_in:
            started = any(a.status != "pending" for a in required)
            out["access_in"] = ("progress" if started else "todo", f"Outstanding: {_join(not_in)}")
        else:
            out["access_in"] = ("done", "")
        if not_ok:
            some = any(a.status == "verified" for a in required)
            out["access_ok"] = ("progress" if some else "todo", f"Not verified: {_join(not_ok)}")
        else:
            out["access_ok"] = ("done", "")

    if snap.kpis_total == 0:
        out["kpi"] = ("todo", "No KPI targets")
    elif snap.kpis_unconfirmed:
        out["kpi"] = ("progress", f"{snap.kpis_unconfirmed} awaiting client confirmation")
    else:
        out["kpi"] = ("done", "")

    out["kickoff_client"] = _meeting_step(snap.kickoff_client, "Kickoff call")

    team_ok = snap.team_size > 0
    internal_state, internal_detail = _meeting_step(snap.kickoff_internal, "Internal kickoff")
    if internal_state == "done" and not team_ok:
        out["kickoff_internal"] = ("progress", "No team assigned")
    elif internal_state != "done" and team_ok:
        out["kickoff_internal"] = ("progress", internal_detail)
    elif internal_state == "todo":
        out["kickoff_internal"] = ("todo", "No team assigned; no internal kickoff scheduled")
    else:
        out["kickoff_internal"] = (internal_state, internal_detail)

    pre = all(out[key][0] == "done" for key in PRE_REVIEW)
    if snap.reviewed and pre:
        out["review"] = ("done", "")
    elif pre:
        out["review"] = ("progress", "Ready for review")
    else:
        out["review"] = ("todo", "Earlier steps incomplete")

    if snap.completed:
        out["done"] = ("done", "")
    elif snap.reviewed and pre:
        out["done"] = ("progress", "Ready to complete")
    else:
        out["done"] = ("todo", "")

    if snap.has_project:
        out["project"] = ("done", "")
    elif snap.completed:
        out["project"] = ("progress", "Start a service from the client profile")
    else:
        out["project"] = ("todo", "Available after onboarding is completed")

    if snap.completed:  # completion freezes steps 1–12 as done
        for key in STEP_KEYS[:12]:
            out[key] = ("done", "")

    steps = tuple(
        Step(number=i + 1, key=key, label=label, hint=hint, state=out[key][0], detail=out[key][1])
        for i, (key, label, hint) in enumerate(STEP_DEFS)
    )
    done = sum(1 for s in steps if s.state == "done")
    blocked = any(s.state == "blocked" for s in steps)
    status: OverallStatus = (
        "completed" if snap.completed else "blocked" if blocked else "in_progress"
    )
    return Evaluation(
        steps=steps, progress=round(done / len(steps) * 100), blocked=blocked, status=status
    )
