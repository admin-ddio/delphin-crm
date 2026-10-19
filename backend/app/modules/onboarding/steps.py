"""The 13 onboarding steps, computed from a snapshot. Pure: no database, no I/O.

Direct port of the clickable demo's `steps(c)` (state per step, detail line,
progress = done ÷ 13, blocked when any required access item is rejected).
TODO(pilot-port): diff against services/onboarding.ts and docs/onboarding-workflow.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final, Literal

StepState = Literal["todo", "progress", "done", "blocked"]
OverallStatus = Literal["in_progress", "blocked", "completed"]

STEP_DEFS: Final[tuple[tuple[str, str, str], ...]] = (
    ("contract", "Contract signed", "Record the contract and mark it signed."),
    ("created", "Client created", ""),
    (
        "profile",
        "Client profile completed",
        "Fill in website, industry and a primary contact with e-mail.",
    ),
    ("q_sent", "Onboarding questionnaire sent", "Send the questionnaire link to the client."),
    ("q_done", "Questionnaire submitted", "Record the client's answers."),
    ("access_in", "Platform access collected", "Mark each platform as received."),
    ("access_ok", "Access verified", "An authorised team member verifies every item."),
    (
        "kpi",
        "KPI targets defined & confirmed",
        "Add KPI targets and record the client's confirmation.",
    ),
    ("kickoff_client", "Client kickoff meeting", "Hold and complete the client kickoff."),
    (
        "kickoff_internal",
        "Internal team kickoff",
        "Assign the team and complete the internal kickoff.",
    ),
    ("review", "Onboarding review", "Pass the review checklist."),
    ("done", "Onboarding completed", "Complete onboarding."),
    ("project", "Project created / linked", "Create the delivery project."),
)
STEP_KEYS: Final = tuple(key for key, _, _ in STEP_DEFS)
#: Steps 1–10 must be done before the review can pass.
PRE_REVIEW: Final = STEP_KEYS[:10]

DEFAULT_ACCESS_ITEMS: Final = (
    ("GSC", "Google Search Console"),
    ("GA4", "Google Analytics 4"),
    ("CMS", "Website CMS"),
    ("AHREFS", "Ahrefs"),
    ("GDRIVE", "Google Drive"),
)

QUESTIONS: Final = (
    ("business_goals", "Business goals"),
    ("products_services", "Products and services"),
    ("target_markets", "Target markets"),
    ("target_audiences", "Target audiences"),
    ("competitors", "Competitors"),
    ("brand_voice", "Brand voice"),
)


@dataclass(frozen=True, slots=True)
class AccessSnapshot:
    label: str
    status: str


@dataclass(frozen=True, slots=True)
class Snapshot:
    website: str | None = None
    industry: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    contract: str = "none"
    questionnaire: str = "none"
    access: tuple[AccessSnapshot, ...] = field(
        default_factory=lambda: tuple(
            AccessSnapshot(label, "pending") for _, label in DEFAULT_ACCESS_ITEMS
        )
    )
    kpis_total: int = 0
    kpis_unconfirmed: int = 0
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


def _join(names: list[str]) -> str:
    return ", ".join(names)


def evaluate(snap: Snapshot) -> Evaluation:  # noqa: PLR0912, PLR0915  # mirrors the demo step by step
    out: dict[str, tuple[StepState, str]] = {}

    if snap.contract == "signed":
        out["contract"] = ("done", "")
    elif snap.contract == "draft":
        out["contract"] = ("progress", "Recorded, not yet signed")
    else:
        out["contract"] = ("todo", "No contract recorded")

    out["created"] = ("done", "")

    missing = [
        name
        for name, ok in (
            ("website", bool(snap.website)),
            ("industry", bool(snap.industry)),
            ("primary contact", bool(snap.contact_name and snap.contact_email)),
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

    if snap.kickoff_client == "done":
        out["kickoff_client"] = ("done", "")
    elif snap.kickoff_client == "scheduled":
        out["kickoff_client"] = ("progress", "Scheduled, not completed")
    else:
        out["kickoff_client"] = ("todo", "Not scheduled")

    team_ok = snap.team_size > 0
    internal_problems = [
        p
        for p in (
            "" if team_ok else "No team assigned",
            "" if snap.kickoff_internal == "done" else "Internal kickoff not completed",
        )
        if p
    ]
    if snap.kickoff_internal == "done" and team_ok:
        out["kickoff_internal"] = ("done", "")
    elif team_ok or snap.kickoff_internal != "none":
        out["kickoff_internal"] = ("progress", "; ".join(internal_problems))
    else:
        out["kickoff_internal"] = ("todo", "; ".join(internal_problems))

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
        out["project"] = ("progress", "Create the delivery project")
    else:
        out["project"] = ("todo", "Available after onboarding is completed")

    if snap.completed:  # completion freezes steps 1–12 as done (demo)
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
