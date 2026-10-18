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
ONBOARDING_MANAGE: Final = "onboarding.manage"
ONBOARDING_ACCESS_VERIFY: Final = "onboarding.access_verify"
ONBOARDING_KPI_CONFIRM: Final = "onboarding.kpi_confirm"
PROJECTS_CREATE: Final = "projects.create"
TASKS_CREATE: Final = "tasks.create"
TASKS_REVIEW: Final = "tasks.review"
APPROVALS_CLIENT_DECISION: Final = "approvals.client_decision"
SERVICES_MANAGE: Final = "services.manage"
JOBS_RUN: Final = "jobs.run"
FINANCE_MANAGE: Final = "finance.manage"
FINANCE_VIEW: Final = "finance.view"
# Approve or reject self sign-ups (only Super Admin has it until permissions.ts is ported).
USERS_APPROVE: Final = "users.approve"

CATALOGUE_SOURCE: Literal["clickable-demo", "pilot"] = "clickable-demo"
CATALOGUE: frozenset[str] = frozenset(
    {
        CLIENTS_CREATE,
        ONBOARDING_MANAGE,
        ONBOARDING_ACCESS_VERIFY,
        ONBOARDING_KPI_CONFIRM,
        PROJECTS_CREATE,
        TASKS_CREATE,
        TASKS_REVIEW,
        APPROVALS_CLIENT_DECISION,
        SERVICES_MANAGE,
        JOBS_RUN,
        FINANCE_MANAGE,
        FINANCE_VIEW,
        USERS_APPROVE,
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
                ONBOARDING_MANAGE,
                ONBOARDING_ACCESS_VERIFY,
                ONBOARDING_KPI_CONFIRM,
                PROJECTS_CREATE,
                TASKS_CREATE,
                APPROVALS_CLIENT_DECISION,
                SERVICES_MANAGE,
                FINANCE_VIEW,
            }
        ),
    ),
    RoleDefinition(
        "project_manager",
        "Project Manager",
        "",
        frozenset(
            {PROJECTS_CREATE, TASKS_CREATE, TASKS_REVIEW, ONBOARDING_ACCESS_VERIFY, JOBS_RUN}
        ),
    ),
    RoleDefinition(
        "team_lead",
        "Team Lead",
        "",
        frozenset({TASKS_CREATE, TASKS_REVIEW, ONBOARDING_ACCESS_VERIFY}),
    ),
    RoleDefinition("employee", "Employee / Specialist"),
    RoleDefinition("finance", "Finance", "", frozenset({FINANCE_MANAGE, FINANCE_VIEW})),
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
