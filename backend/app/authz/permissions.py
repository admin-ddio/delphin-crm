"""Permission catalogue and default role definitions.

INTERIM SOURCE: the clickable demo's role/capability matrix
(reference/pilot/clickable-demo/delphin-agency-demo.html, see
docs/clickable-demo-findings.md), renamed to `domain.action` strings, plus the
product owner's HR and Organization Structure briefs (2026-10).
The source of truth is reference/pilot/nextjs-app/src/server/authz/permissions.ts,
not present yet. Until it is ported:

- CATALOGUE_SOURCE is "clickable-demo", so require_permission() validates the
  string's format only (feature ports may use the pilot's real strings);
- `admin` (in the scaffold brief, absent from the demo) has no permissions.

Roles live in the database and are edited in Organization & Role Settings
(`org.roles.manage`). DEFAULT_ROLES only seeds missing roles; permission changes
for existing roles ship as migrations, so admins' edits are never overwritten.

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
# Services plan (2026-10): see every client service; edit the service task templates.
SERVICES_VIEW_ALL: Final = "services.view_all"
SERVICES_TEMPLATES_MANAGE: Final = "services.templates.manage"
JOBS_RUN: Final = "jobs.run"
FINANCE_MANAGE: Final = "finance.manage"
FINANCE_VIEW: Final = "finance.view"
# Approve or reject self sign-ups (only Super Admin has it until permissions.ts is ported).
USERS_APPROVE: Final = "users.approve"
# Invite people and deactivate / reactivate sign-in accounts (Team & Roles).
USERS_MANAGE: Final = "users.manage"
# Schedule and run client meetings (AM, PM, Team Lead; the client's AM and team too).
MEETINGS_MANAGE: Final = "meetings.manage"
# HR: employee records and employment details (EDIT_EMPLOYEE_PROFILE); see every
# employee's employment details; see others' personal information.
HR_MANAGE: Final = "hr.manage"
HR_VIEW_ALL: Final = "hr.view_all"
HR_PERSONAL_VIEW: Final = "hr.personal.view"
# Organization Structure & Role Settings (brief §8). Scoped to that module only.
ORG_VIEW: Final = "org.view"  # VIEW_ORGANIZATION_STRUCTURE
ORG_DIRECTORY_VIEW: Final = "org.directory.view"  # VIEW_EMPLOYEE_DIRECTORY
ORG_TEAM_VIEW: Final = "org.team.view"  # VIEW_TEAM_INFORMATION
ORG_DEPARTMENTS_MANAGE: Final = "org.departments.manage"  # MANAGE_DEPARTMENTS
ORG_DESIGNATIONS_MANAGE: Final = "org.designations.manage"  # MANAGE_DESIGNATIONS
ORG_REPORTING_MANAGE: Final = "org.reporting.manage"  # MANAGE_REPORTING_HIERARCHY
ORG_PROJECTS_ASSIGN: Final = "org.projects.assign"  # MANAGE_PROJECT_ASSIGNMENTS
ORG_ROLES_MANAGE: Final = "org.roles.manage"  # MANAGE_ROLE_DEFINITIONS
ORG_ROLES_ASSIGN: Final = "org.roles.assign"  # ASSIGN_EMPLOYEE_ROLES
ORG_AUDIT_VIEW: Final = "org.audit.view"  # VIEW_ORGANIZATION_AUDIT_LOG

#: Matrix labels: permission → (module, label). Every catalogued permission has one.
PERMISSION_INFO: Final[dict[str, tuple[str, str]]] = {
    CLIENTS_CREATE: ("Clients", "Create clients"),
    CLIENTS_VIEW_ALL: ("Clients", "See every client"),
    CLIENTS_UPDATE: ("Clients", "Edit own clients"),
    ONBOARDING_MANAGE: ("Client onboarding", "Run onboarding for own clients"),
    ONBOARDING_ACCESS_VERIFY: ("Client onboarding", "Verify platform access"),
    ONBOARDING_KPI_CONFIRM: ("Client onboarding", "Record KPI confirmations"),
    MEETINGS_MANAGE: ("Client onboarding", "Schedule and run client meetings"),
    PROJECTS_CREATE: ("Projects & tasks", "Create projects"),
    PROJECTS_VIEW_ALL: ("Projects & tasks", "See every project"),
    TASKS_CREATE: ("Projects & tasks", "Create tasks"),
    TASKS_REVIEW: ("Projects & tasks", "Review tasks"),
    APPROVALS_CLIENT_DECISION: ("Projects & tasks", "Record client decisions"),
    SERVICES_MANAGE: ("Services & finance", "Manage services & retainers"),
    SERVICES_VIEW_ALL: ("Services & finance", "See every client service"),
    SERVICES_TEMPLATES_MANAGE: ("Services & finance", "Edit service task templates"),
    FINANCE_MANAGE: ("Services & finance", "Manage finance"),
    FINANCE_VIEW: ("Services & finance", "View finance"),
    JOBS_RUN: ("System", "Run background jobs"),
    USERS_APPROVE: ("System", "Approve sign-ups"),
    USERS_MANAGE: ("System", "Invite and deactivate accounts"),
    HR_MANAGE: ("Employees (HR)", "Edit employee profiles"),
    HR_VIEW_ALL: ("Employees (HR)", "See everyone's employment details"),
    HR_PERSONAL_VIEW: ("Employees (HR)", "See personal details"),
    ORG_VIEW: ("Organization & roles", "View organization structure"),
    ORG_DIRECTORY_VIEW: ("Organization & roles", "View employee directory"),
    ORG_TEAM_VIEW: ("Organization & roles", "View team information"),
    ORG_DEPARTMENTS_MANAGE: ("Organization & roles", "Manage departments"),
    ORG_DESIGNATIONS_MANAGE: ("Organization & roles", "Manage designations"),
    ORG_REPORTING_MANAGE: ("Organization & roles", "Manage reporting hierarchy"),
    ORG_PROJECTS_ASSIGN: ("Organization & roles", "Manage project assignments"),
    ORG_ROLES_MANAGE: ("Organization & roles", "Manage role definitions"),
    ORG_ROLES_ASSIGN: ("Organization & roles", "Assign employee roles"),
    ORG_AUDIT_VIEW: ("Organization & roles", "View organization audit log"),
}

CATALOGUE_SOURCE: Literal["clickable-demo", "pilot"] = "clickable-demo"
CATALOGUE: frozenset[str] = frozenset(PERMISSION_INFO)

#: Everyone signed in may look at the organisation and the directory.
EVERYONE: Final = frozenset({ORG_VIEW, ORG_DIRECTORY_VIEW})
ORG_ADMIN_PERMISSIONS: Final = frozenset(
    {
        ORG_VIEW,
        ORG_DIRECTORY_VIEW,
        ORG_TEAM_VIEW,
        ORG_DEPARTMENTS_MANAGE,
        ORG_DESIGNATIONS_MANAGE,
        ORG_REPORTING_MANAGE,
        ORG_PROJECTS_ASSIGN,
        ORG_ROLES_MANAGE,
        ORG_ROLES_ASSIGN,
        ORG_AUDIT_VIEW,
    }
)


@dataclass(frozen=True, slots=True)
class RoleDefinition:
    key: str
    name: str
    description: str = ""
    permissions: frozenset[str] = field(default_factory=frozenset)


SUPER_ADMIN: Final = "super_admin"
ORG_ADMIN: Final = "org_admin"

DEFAULT_ROLES: Final[tuple[RoleDefinition, ...]] = (
    RoleDefinition(SUPER_ADMIN, "Super Admin", "", frozenset({WILDCARD})),
    # In the scaffold brief, not in the demo: permissions unknown until permissions.ts.
    RoleDefinition("admin", "Admin / Operations Manager", "", EVERYONE),
    RoleDefinition(
        "account_manager",
        "Account Manager",
        "",
        EVERYONE
        | {
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
            SERVICES_VIEW_ALL,
            FINANCE_VIEW,
            MEETINGS_MANAGE,
            ORG_TEAM_VIEW,
        },
    ),
    RoleDefinition(
        "project_manager",
        "Project Manager",
        "",
        EVERYONE
        | {
            CLIENTS_VIEW_ALL,
            PROJECTS_CREATE,
            PROJECTS_VIEW_ALL,
            TASKS_CREATE,
            TASKS_REVIEW,
            ONBOARDING_ACCESS_VERIFY,
            JOBS_RUN,
            MEETINGS_MANAGE,
            ORG_TEAM_VIEW,
            ORG_PROJECTS_ASSIGN,
            SERVICES_VIEW_ALL,
            SERVICES_TEMPLATES_MANAGE,
        },
    ),
    RoleDefinition(
        "team_lead",
        "Team Lead",
        "",
        EVERYONE
        | {TASKS_CREATE, TASKS_REVIEW, ONBOARDING_ACCESS_VERIFY, MEETINGS_MANAGE, ORG_TEAM_VIEW},
    ),
    RoleDefinition("employee", "Employee / Specialist", "", EVERYONE),
    RoleDefinition(
        "finance",
        "Finance",
        "",
        EVERYONE
        | {CLIENTS_VIEW_ALL, PROJECTS_VIEW_ALL, FINANCE_MANAGE, FINANCE_VIEW, SERVICES_VIEW_ALL},
    ),
    # HR brief: employee records and personal details. Org structure moved to org_admin.
    RoleDefinition(
        "hr_admin",
        "HR / Operations Admin",
        "",
        EVERYONE | {HR_MANAGE, HR_VIEW_ALL, HR_PERSONAL_VIEW, ORG_TEAM_VIEW},
    ),
    # Organization brief §7: org structure, reporting and roles, nothing outside that module.
    RoleDefinition(
        ORG_ADMIN,
        "Organization Admin",
        "Departments, designations, reporting lines and role definitions only.",
        ORG_ADMIN_PERMISSIONS,
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
