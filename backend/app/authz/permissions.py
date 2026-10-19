"""Permission catalogue and default role definitions.

INTERIM SOURCE: the clickable demo's role/capability matrix
(reference/pilot/clickable-demo/delphin-agency-demo.html, see
docs/clickable-demo-findings.md), renamed to `domain.action` strings.
The source of truth is reference/pilot/nextjs-app/src/server/authz/permissions.ts,
not present yet. Until it is ported:

- CATALOGUE_SOURCE is "clickable-demo", so require_permission() validates the
  string's format only (feature ports may use the pilot's real strings);
- `admin` (in the scaffold brief, absent from the demo) has no permissions.

When porting: replace CATALOGUE and DEFAULT_ROLES verbatim, set
CATALOGUE_SOURCE = "pilot", and the pending test in test_permissions.py runs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Final, Literal

WILDCARD: Final = "*"
_PERMISSION_FORMAT = re.compile(r"[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+")

CLIENTS_CREATE: Final = "clients.create"
# Demo: AM, PM and Finance see every client; others only clients they work on.
CLIENTS_VIEW_ALL: Final = "clients.view_all"
# Demo: the client's own Account Manager (or Super Admin) manages it.
CLIENTS_UPDATE: Final = "clients.update"
ONBOARDING_MANAGE: Final = "onboarding.manage"
ONBOARDING_ACCESS_VERIFY: Final = "onboarding.access_verify"
ONBOARDING_KPI_CONFIRM: Final = "onboarding.kpi_confirm"
PROJECTS_CREATE: Final = "projects.create"
# Demo: AM, PM and Finance see every project; others only projects they work on.
PROJECTS_VIEW_ALL: Final = "projects.view_all"
TASKS_CREATE: Final = "tasks.create"
TASKS_REVIEW: Final = "tasks.review"
APPROVALS_CLIENT_DECISION: Final = "approvals.client_decision"
SERVICES_MANAGE: Final = "services.manage"
JOBS_RUN: Final = "jobs.run"
FINANCE_MANAGE: Final = "finance.manage"
FINANCE_VIEW: Final = "finance.view"
# Approve or reject self sign-ups (only Super Admin has it until permissions.ts is ported).
USERS_APPROVE: Final = "users.approve"
# HR (interim, from the HR brief): manage people records and the organisation;
# see every employee's employment details; see others' personal information.
# Schedule and run client meetings (AM, PM, Team Lead; the client's AM and team too).
MEETINGS_MANAGE: Final = "meetings.manage"
HR_MANAGE: Final = "hr.manage"
HR_VIEW_ALL: Final = "hr.view_all"
HR_PERSONAL_VIEW: Final = "hr.personal.view"

CATALOGUE_SOURCE: Literal["clickable-demo", "pilot"] = "clickable-demo"
CATALOGUE: frozenset[str] = frozenset(
    {
        CLIENTS_CREATE,
        CLIENTS_VIEW_ALL,
        CLIENTS_UPDATE,
        ONBOARDING_MANAGE,
        ONBOARDING_ACCESS_VERIFY,
        ONBOARDING_KPI_CONFIRM,
        PROJECTS_CREATE,
        PROJECTS_VIEW_ALL,
        TASKS_CREATE,
        TASKS_REVIEW,
        APPROVALS_CLIENT_DECISION,
        SERVICES_MANAGE,
        JOBS_RUN,
        FINANCE_MANAGE,
        FINANCE_VIEW,
        USERS_APPROVE,
        MEETINGS_MANAGE,
        HR_MANAGE,
        HR_VIEW_ALL,
        HR_PERSONAL_VIEW,
    }
)


@dataclass(frozen=True, slots=True)
class RoleDefinition:
    key: str
    name: str
    description: str = ""
    permissions: frozenset[str] = field(default_factory=frozenset)


SUPER_ADMIN: Final = "super_admin"

DEFAULT_ROLES: Final[tuple[RoleDefinition, ...]] = (
    RoleDefinition(SUPER_ADMIN, "Super Admin", "", frozenset({WILDCARD})),
    # In the scaffold brief, not in the demo: permissions unknown until permissions.ts.
    RoleDefinition("admin", "Admin / Operations Manager"),
    RoleDefinition(
        "account_manager",
        "Account Manager",
        "",
        frozenset(
            {
                CLIENTS_CREATE,
                CLIENTS_VIEW_ALL,
                CLIENTS_UPDATE,
                ONBOARDING_MANAGE,
                ONBOARDING_ACCESS_VERIFY,
                ONBOARDING_KPI_CONFIRM,
                PROJECTS_CREATE,
                TASKS_CREATE,
                PROJECTS_VIEW_ALL,
                APPROVALS_CLIENT_DECISION,
                SERVICES_MANAGE,
                FINANCE_VIEW,
                MEETINGS_MANAGE,
            }
        ),
    ),
    RoleDefinition(
        "project_manager",
        "Project Manager",
        "",
        frozenset(
            {
                CLIENTS_VIEW_ALL,
                PROJECTS_CREATE,
                PROJECTS_VIEW_ALL,
                TASKS_CREATE,
                TASKS_REVIEW,
                ONBOARDING_ACCESS_VERIFY,
                JOBS_RUN,
                MEETINGS_MANAGE,
            }
        ),
    ),
    RoleDefinition(
        "team_lead",
        "Team Lead",
        "",
        frozenset({TASKS_CREATE, TASKS_REVIEW, ONBOARDING_ACCESS_VERIFY, MEETINGS_MANAGE}),
    ),
    RoleDefinition("employee", "Employee / Specialist"),
    RoleDefinition(
        "finance",
        "Finance",
        "",
        frozenset({CLIENTS_VIEW_ALL, PROJECTS_VIEW_ALL, FINANCE_MANAGE, FINANCE_VIEW}),
    ),
    # From the HR brief: onboarding, profiles, departments and reporting lines.
    RoleDefinition(
        "hr_admin",
        "HR / Operations Admin",
        "",
        frozenset({HR_MANAGE, HR_VIEW_ALL, HR_PERSONAL_VIEW}),
    ),
)


def is_catalogue_ported() -> bool:
    """True only once the catalogue comes from the pilot's permissions.ts."""
    return CATALOGUE_SOURCE == "pilot"


def validate_permission(name: str) -> str:
    """Return name if it is a well-formed (and, once ported, catalogued) permission."""
    if name == WILDCARD:
        return name
    if not _PERMISSION_FORMAT.fullmatch(name):
        msg = f"Malformed permission string: {name!r} (expected 'domain.action')"
        raise ValueError(msg)
    if is_catalogue_ported() and name not in CATALOGUE:
        msg = f"Unknown permission: {name!r} is not in the catalogue"
        raise ValueError(msg)
    return name
