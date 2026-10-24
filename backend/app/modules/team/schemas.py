"""Request/response models for the team module: sign-up approvals and people core."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, EmailStr, Field

# ---------------------------------------------------------------- sign-up approvals


class PendingRegistration(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    registered_at: datetime
    # None when the Firebase account no longer exists.
    email_verified: bool | None


class ApproveRegistrationRequest(BaseModel):
    role: str = Field(min_length=1, max_length=64)


# ---------------------------------------------------------------- people core


def _strip(value: object) -> object:
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


Text = Annotated[str | None, BeforeValidator(_strip)]
EmploymentType = Literal["full_time", "part_time", "intern", "contractor", "consultant"]
WorkArrangement = Literal["remote", "hybrid", "office"]
EmployeeStatus = Literal["onboarding", "probation", "active", "notice", "on_hold", "exited"]


class Ref(BaseModel):
    id: uuid.UUID
    name: str


class PersonRef(BaseModel):
    id: uuid.UUID
    code: str
    full_name: str


class EmployeeListItem(BaseModel):
    id: uuid.UUID
    code: str
    full_name: str
    preferred_name: str | None
    official_email: str | None
    designation: Ref | None
    department: Ref | None
    manager: PersonRef | None
    status: EmployeeStatus
    status_label: str
    is_executive: bool
    #: The linked sign-in account (for workload views); None if not linked.
    user_id: uuid.UUID | None
    is_me: bool


ReportingKind = Literal[
    "direct_manager",
    "functional_manager",
    "project_manager",
    "department_head",
    "leave_approver",
    "performance_reviewer",
    "executive_escalation",
]
#: explicit: a reporting line on the employee; department: inherited from the department
#: (owners, delivery manager, head); direct_manager / functional_manager: an approver
#: falling back to that relationship.
RelationSource = Literal["explicit", "department", "direct_manager", "functional_manager"]


class ProjectRef(BaseModel):
    id: uuid.UUID
    code: str | None
    name: str


class Relation(BaseModel):
    kind: ReportingKind
    kind_label: str
    manager: PersonRef
    source: RelationSource
    project: ProjectRef | None = None
    starts_on: date | None = None


class Employment(BaseModel):
    """Visible to the employee, their managers / department head, and `hr.view_all`."""

    employment_type: EmploymentType
    work_arrangement: WorkArrangement | None
    joining_date: date | None
    #: Every relationship that applies (explicit or inherited from the department).
    reporting: list[Relation]
    #: The leave approver that applies (explicit, else direct manager, else functional).
    effective_leave_approver: PersonRef | None
    department_head: PersonRef | None
    has_account: bool


class Personal(BaseModel):
    """Visible to the employee and `hr.personal.view` only."""

    personal_email: str | None
    phone: str | None
    date_of_birth: date | None
    current_address: str | None
    permanent_address: str | None
    emergency_name: str | None
    emergency_relationship: str | None
    emergency_phone: str | None


class EmployeePermissions(BaseModel):
    manage: bool
    edit_personal: bool
    #: Department, designation and reporting lines (`org.reporting.manage`).
    manage_reporting: bool


class EmployeeDetail(EmployeeListItem):
    created_at: datetime
    direct_reports: list[PersonRef]
    #: None when the viewer may not see it.
    employment: Employment | None
    personal: Personal | None
    permissions: EmployeePermissions


class EmployeeCreate(BaseModel):
    full_name: Annotated[str, BeforeValidator(_strip)] = Field(min_length=1, max_length=200)
    preferred_name: Text = Field(default=None, max_length=100)
    official_email: EmailStr | None = None
    department_id: uuid.UUID | None = None
    designation_id: uuid.UUID | None = None
    employment_type: EmploymentType = "full_time"
    work_arrangement: WorkArrangement | None = None
    status: Literal["onboarding", "probation", "active"] = "onboarding"
    joining_date: date | None = None
    #: Needs `org.reporting.manage` (as do department and designation).
    manager_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None


class EmployeeUpdate(BaseModel):
    """Partial: only fields sent are changed. Department, designation, `is_executive` and
    `manager_id` (null removes the direct manager) need `org.reporting.manage`; the
    rest `hr.manage`."""

    full_name: Text = Field(default=None, max_length=200)
    preferred_name: Text = Field(default=None, max_length=100)
    official_email: EmailStr | None = None
    department_id: uuid.UUID | None = None
    designation_id: uuid.UUID | None = None
    employment_type: EmploymentType | None = None
    work_arrangement: WorkArrangement | None = None
    status: EmployeeStatus | None = None
    joining_date: date | None = None
    is_executive: bool | None = None
    manager_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None


class PersonalUpdate(BaseModel):
    preferred_name: Text = Field(default=None, max_length=100)
    personal_email: EmailStr | None = None
    phone: Text = Field(default=None, max_length=40)
    date_of_birth: date | None = None
    current_address: Text = Field(default=None, max_length=1000)
    permanent_address: Text = Field(default=None, max_length=1000)
    emergency_name: Text = Field(default=None, max_length=200)
    emergency_relationship: Text = Field(default=None, max_length=100)
    emergency_phone: Text = Field(default=None, max_length=40)


class EmploymentEventOut(BaseModel):
    id: uuid.UUID
    kind: str
    summary: str
    effective_on: date | None
    occurred_at: datetime
    actor: str | None
    changes: dict[str, Any] | None


class UserOption(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str


class DepartmentOut(BaseModel):
    id: uuid.UUID
    name: str
    #: The department's purpose.
    description: str | None
    head: PersonRef | None
    #: Executive owners: the default functional managers of the department's members.
    owners: list[PersonRef]
    #: Default Project Manager for members' delivery reporting.
    delivery_manager: PersonRef | None
    headcount: int
    is_active: bool


class DepartmentIn(BaseModel):
    name: Annotated[str, BeforeValidator(_strip)] = Field(min_length=1, max_length=100)
    description: Text = Field(default=None, max_length=1000)
    head_id: uuid.UUID | None = None
    owner_ids: list[uuid.UUID] = Field(default_factory=list, max_length=10)
    delivery_manager_id: uuid.UUID | None = None


class DepartmentUpdate(BaseModel):
    """Partial. `owner_ids` replaces the owners; null `head_id` / `delivery_manager_id`
    clears them; `is_active` deactivates (only when empty) or reactivates."""

    name: Text = Field(default=None, max_length=100)
    description: Text = Field(default=None, max_length=1000)
    head_id: uuid.UUID | None = None
    owner_ids: list[uuid.UUID] | None = Field(default=None, max_length=10)
    delivery_manager_id: uuid.UUID | None = None
    is_active: bool | None = None


class DesignationOut(BaseModel):
    id: uuid.UUID
    name: str
    #: None for company-level titles (e.g. Founder & CEO).
    department: Ref | None
    is_active: bool
    headcount: int


class DesignationIn(BaseModel):
    name: Annotated[str, BeforeValidator(_strip)] = Field(min_length=1, max_length=100)
    department_id: uuid.UUID | None = None


class DesignationUpdate(BaseModel):
    name: Text = Field(default=None, max_length=100)
    department_id: uuid.UUID | None = None
    is_active: bool | None = None


# ---------------------------------------------------------------- reporting relationships


class ReportingLineOut(BaseModel):
    id: uuid.UUID
    kind: ReportingKind
    kind_label: str
    manager: PersonRef
    project: ProjectRef | None
    starts_on: date
    ends_on: date | None
    active: bool
    created_by: str | None
    ended_by: str | None


class Reporting(BaseModel):
    employee: PersonRef
    department: Ref | None
    #: Open explicit lines (what the editor edits).
    lines: list[ReportingLineOut]
    #: What applies now: explicit lines plus department defaults and approver fallbacks.
    effective: list[Relation]
    #: Every line ever recorded, newest first (ended lines are kept).
    history: list[ReportingLineOut]
    can_edit: bool
    #: True when only Project Manager lines may be changed (`org.projects.assign`).
    projects_only: bool


class ReportingLineIn(BaseModel):
    kind: ReportingKind
    manager_id: uuid.UUID
    project_id: uuid.UUID | None = None


class ReportingChange(BaseModel):
    """The complete set of explicit lines the employee should have. Lines not listed
    are ended on `effective_on` (default today); new ones start that day."""

    lines: list[ReportingLineIn] = Field(max_length=50)
    effective_on: date | None = None


class LineChange(BaseModel):
    kind: ReportingKind
    kind_label: str
    manager: PersonRef
    project: ProjectRef | None


class ReportingPreview(BaseModel):
    valid: bool
    errors: list[str]
    added: list[LineChange]
    ended: list[LineChange]
    #: Effective relationships after the change.
    effective: list[Relation]
    #: The organisation chart with the change applied.
    chart: OrgChart


class ProjectOption(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    #: The project's manager, when that sign-in account is linked to an employee.
    manager: PersonRef | None


# ---------------------------------------------------------------- org chart


class ChartMember(BaseModel):
    id: uuid.UUID
    code: str
    full_name: str
    designation: Ref | None
    department_id: uuid.UUID | None
    status: EmployeeStatus
    status_label: str
    is_executive: bool
    relations: list[Relation]
    #: Unresolved assignments, e.g. "No functional manager".
    issues: list[str]


class ChartDepartment(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    is_active: bool
    head: PersonRef | None
    owners: list[PersonRef]
    delivery_manager: PersonRef | None
    members: list[ChartMember]
    #: Unassigned head / owner / delivery manager.
    issues: list[str]


class DeliveryProject(BaseModel):
    project: ProjectRef
    members: list[PersonRef]


class DeliveryGroup(BaseModel):
    manager: PersonRef
    #: Members whose delivery runs through this PM without a specific project
    #: (explicit or the department default).
    members: list[PersonRef]
    projects: list[DeliveryProject]


class OrgChart(BaseModel):
    executives: list[ChartMember]
    departments: list[ChartDepartment]
    #: Not executives and not in any department.
    unplaced: list[ChartMember]
    delivery: list[DeliveryGroup]


# ---------------------------------------------------------------- roles and permissions


class PermissionInfo(BaseModel):
    key: str
    module: str
    label: str


class RoleOut(BaseModel):
    key: str
    name: str
    description: str | None
    permissions: list[str]
    is_system: bool
    member_count: int
    #: False for Super Admin, roles the viewer holds, and roles above the viewer's authority.
    editable: bool
    #: Whether the viewer may give this role to someone.
    assignable: bool


class RolesOverview(BaseModel):
    catalogue: list[PermissionInfo]
    roles: list[RoleOut]
    can_manage: bool
    can_assign: bool


class RoleIn(BaseModel):
    key: str = Field(min_length=2, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    name: Annotated[str, BeforeValidator(_strip)] = Field(min_length=1, max_length=100)
    description: Text = Field(default=None, max_length=1000)
    permissions: list[str] = Field(default_factory=list, max_length=200)


class RoleUpdate(BaseModel):
    name: Text = Field(default=None, max_length=100)
    description: Text = Field(default=None, max_length=1000)
    permissions: list[str] | None = Field(default=None, max_length=200)


class UserRoles(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str
    roles: list[str]
    employee: PersonRef | None
    #: False for the viewer themself and for users holding roles above the viewer.
    editable: bool


class UserRolesUpdate(BaseModel):
    roles: list[str] = Field(min_length=1, max_length=20)


# ---------------------------------------------------------------- org audit log


class OrgAuditEntry(BaseModel):
    id: uuid.UUID
    occurred_at: datetime
    actor: str | None
    action: str
    entity_type: str
    entity_id: str | None
    changes: dict[str, Any]
    context: dict[str, Any]


ReportingPreview.model_rebuild()
