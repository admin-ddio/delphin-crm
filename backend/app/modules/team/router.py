"""HTTP surface of the team module: sign-up approvals and the people core."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.actor import Actor
from app.authz.dependencies import CurrentActor, require_permission
from app.authz.permissions import USERS_APPROVE
from app.core.clock import Clock, get_clock
from app.core.config import Settings, get_app_settings
from app.core.errors import AUTH_ERROR_RESPONSES, ErrorEnvelope
from app.db.session import get_session
from app.modules.team.schemas import (
    Account,
    AccountsOverview,
    ApproveRegistrationRequest,
    DepartmentIn,
    DepartmentOut,
    DepartmentUpdate,
    DesignationIn,
    DesignationOut,
    DesignationUpdate,
    EmployeeCreate,
    EmployeeDetail,
    EmployeeListItem,
    EmployeeStatus,
    EmployeeUpdate,
    EmploymentEventOut,
    InviteRequest,
    InviteResult,
    OrgAuditEntry,
    OrgChart,
    PendingRegistration,
    PersonalUpdate,
    ProjectOption,
    Reporting,
    ReportingChange,
    ReportingPreview,
    RoleIn,
    RoleOut,
    RolesOverview,
    RoleUpdate,
    UserOption,
    UserRoles,
    UserRolesUpdate,
)
from app.modules.team.service import AccountsService, OrgService, PeopleService, TeamService
from app.platform.identity.firebase import IdentityProvider, get_identity_provider

TAG = {"name": "team", "description": "Team & Employees, teams, workload, sign-up approvals"}

router = APIRouter(prefix="/team", tags=["team"])

Approver = Annotated[Actor, Depends(require_permission(USERS_APPROVE))]
NOT_PENDING: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorEnvelope, "description": "Not pending (or already handled)"}
}


def get_team_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    clock: Annotated[Clock, Depends(get_clock)],
    identity: Annotated[IdentityProvider, Depends(get_identity_provider)],
) -> TeamService:
    return TeamService(session, clock=clock, identity=identity)


Service = Annotated[TeamService, Depends(get_team_service)]


@router.get(
    "/registrations", response_model=list[PendingRegistration], responses=AUTH_ERROR_RESPONSES
)
async def list_pending_registrations(
    actor: Approver, service: Service
) -> list[PendingRegistration]:
    """Self sign-ups waiting for approval, oldest first."""
    return await service.pending_registrations()


@router.post(
    "/registrations/{user_id}/approve",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses={**AUTH_ERROR_RESPONSES, **NOT_PENDING},
)
async def approve_registration(
    user_id: uuid.UUID, body: ApproveRegistrationRequest, actor: Approver, service: Service
) -> None:
    await service.approve(actor, user_id, body.role)


@router.post(
    "/registrations/{user_id}/reject",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses={**AUTH_ERROR_RESPONSES, **NOT_PENDING},
)
async def reject_registration(user_id: uuid.UUID, actor: Approver, service: Service) -> None:
    await service.reject(actor, user_id)


# ==================================================================== people core

ERRORS: dict[int | str, dict[str, Any]] = {
    **AUTH_ERROR_RESPONSES,
    404: {"model": ErrorEnvelope, "description": "Not found"},
    409: {"model": ErrorEnvelope, "description": "Duplicate e-mail, account link or name"},
    422: {"model": ErrorEnvelope, "description": "Validation failed or business rule violated"},
}


def get_people_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> PeopleService:
    return PeopleService(session, clock=clock)


People = Annotated[PeopleService, Depends(get_people_service)]


@router.get("/employees", response_model=list[EmployeeListItem], responses=AUTH_ERROR_RESPONSES)
async def list_employees(
    *,
    actor: CurrentActor,
    service: People,
    q: Annotated[str | None, Query(max_length=200, description="Name, code or e-mail")] = None,
    department_id: Annotated[uuid.UUID | None, Query()] = None,
    designation_id: Annotated[uuid.UUID | None, Query()] = None,
    status_filter: Annotated[EmployeeStatus | None, Query(alias="status")] = None,
    include_exited: Annotated[bool, Query()] = False,
) -> list[EmployeeListItem]:
    """The employee directory (`org.directory.view`), alphabetical."""
    return await service.list_employees(
        actor,
        q=q,
        department_id=department_id,
        designation_id=designation_id,
        status=status_filter,
        include_exited=include_exited,
    )


@router.post(
    "/employees",
    status_code=status.HTTP_201_CREATED,
    response_model=EmployeeDetail,
    responses=ERRORS,
)
async def create_employee(
    body: EmployeeCreate, actor: CurrentActor, service: People
) -> EmployeeDetail:
    """`hr.manage` (placement fields also `org.reporting.manage`). Codes are DD-0001…"""
    return await service.create(actor, body)


@router.get("/employees/user-options", response_model=list[UserOption], responses=ERRORS)
async def user_options(actor: CurrentActor, service: People) -> list[UserOption]:
    """`hr.manage`. Active sign-in accounts not yet linked to an employee."""
    return await service.user_options(actor)


@router.get("/employees/{employee_id}", response_model=EmployeeDetail, responses=ERRORS)
async def get_employee(
    employee_id: uuid.UUID, actor: CurrentActor, service: People
) -> EmployeeDetail:
    """Employment and personal sections are null when the viewer may not see them."""
    return await service.get(actor, employee_id)


@router.patch("/employees/{employee_id}", response_model=EmployeeDetail, responses=ERRORS)
async def update_employee(
    employee_id: uuid.UUID, body: EmployeeUpdate, actor: CurrentActor, service: People
) -> EmployeeDetail:
    """Partial. HR fields need `hr.manage`; department, designation, executive flag and
    `manager_id` need `org.reporting.manage` (the direct manager is replaced, history kept)."""
    return await service.update(actor, employee_id, body)


@router.patch("/employees/{employee_id}/personal", response_model=EmployeeDetail, responses=ERRORS)
async def update_personal(
    employee_id: uuid.UUID, body: PersonalUpdate, actor: CurrentActor, service: People
) -> EmployeeDetail:
    """The employee themselves, or `hr.manage`."""
    return await service.update_personal(actor, employee_id, body)


@router.get(
    "/employees/{employee_id}/history", response_model=list[EmploymentEventOut], responses=ERRORS
)
async def employment_history(
    employee_id: uuid.UUID, actor: CurrentActor, service: People
) -> list[EmploymentEventOut]:
    """Newest first. Visible to the employee, their managers and `hr.view_all`."""
    return await service.history(actor, employee_id)


@router.get("/departments", response_model=list[DepartmentOut], responses=AUTH_ERROR_RESPONSES)
async def list_departments(actor: CurrentActor, service: People) -> list[DepartmentOut]:
    """Every department with its owners, head, delivery manager and headcount."""
    return await service.departments()


@router.post(
    "/departments",
    status_code=status.HTTP_201_CREATED,
    response_model=DepartmentOut,
    responses=ERRORS,
)
async def create_department(
    body: DepartmentIn, actor: CurrentActor, service: People
) -> DepartmentOut:
    return await service.create_department(actor, body)


@router.patch("/departments/{department_id}", response_model=DepartmentOut, responses=ERRORS)
async def update_department(
    department_id: uuid.UUID, body: DepartmentUpdate, actor: CurrentActor, service: People
) -> DepartmentOut:
    """`org.departments.manage`. Rename, set owners / head / delivery manager, or
    (de)activate (deactivating only when it has no employees)."""
    return await service.update_department(actor, department_id, body)


@router.get("/designations", response_model=list[DesignationOut], responses=AUTH_ERROR_RESPONSES)
async def list_designations(actor: CurrentActor, service: People) -> list[DesignationOut]:
    return await service.designations()


@router.post(
    "/designations",
    status_code=status.HTTP_201_CREATED,
    response_model=DesignationOut,
    responses=ERRORS,
)
async def create_designation(
    body: DesignationIn, actor: CurrentActor, service: People
) -> DesignationOut:
    return await service.create_designation(actor, body)


@router.patch("/designations/{designation_id}", response_model=DesignationOut, responses=ERRORS)
async def update_designation(
    designation_id: uuid.UUID, body: DesignationUpdate, actor: CurrentActor, service: People
) -> DesignationOut:
    return await service.update_designation(actor, designation_id, body)


# ==================================================================== Organization & Role Settings


def get_org_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> OrgService:
    return OrgService(session, clock=clock)


Organization = Annotated[OrgService, Depends(get_org_service)]


@router.get("/employees/{employee_id}/reporting", response_model=Reporting, responses=ERRORS)
async def get_reporting(
    employee_id: uuid.UUID, actor: CurrentActor, service: Organization
) -> Reporting:
    """`org.view`. Open lines, effective relationships (with department defaults), history."""
    return await service.reporting(actor, employee_id)


@router.post(
    "/employees/{employee_id}/reporting/preview",
    response_model=ReportingPreview,
    responses=ERRORS,
)
async def preview_reporting(
    employee_id: uuid.UUID, body: ReportingChange, actor: CurrentActor, service: Organization
) -> ReportingPreview:
    """Validate a change and return the chart as it would be. Saves nothing."""
    return await service.preview(actor, employee_id, body)


@router.put("/employees/{employee_id}/reporting", response_model=Reporting, responses=ERRORS)
async def change_reporting(
    employee_id: uuid.UUID, body: ReportingChange, actor: CurrentActor, service: Organization
) -> Reporting:
    """`org.reporting.manage` (or `org.projects.assign` for Project Manager lines only).
    `lines` is the full set of open lines; missing ones end on `effective_on`."""
    return await service.change_reporting(actor, employee_id, body)


@router.get("/project-options", response_model=list[ProjectOption], responses=ERRORS)
async def project_options(actor: CurrentActor, service: Organization) -> list[ProjectOption]:
    """Projects that Project Manager lines can point at."""
    return await service.project_options(actor)


@router.get("/org-chart", response_model=OrgChart, responses=ERRORS)
async def org_chart(actor: CurrentActor, service: Organization) -> OrgChart:
    """`org.view`. Executives, departments with members and relationships, delivery groups."""
    return await service.chart(actor)


@router.get("/roles", response_model=RolesOverview, responses=ERRORS)
async def list_roles(actor: CurrentActor, service: Organization) -> RolesOverview:
    """`org.roles.manage` or `org.roles.assign`. The permission matrix."""
    return await service.roles(actor)


@router.post(
    "/roles", status_code=status.HTTP_201_CREATED, response_model=RoleOut, responses=ERRORS
)
async def create_role(body: RoleIn, actor: CurrentActor, service: Organization) -> RoleOut:
    """`org.roles.manage`. Only permissions the actor holds can be granted."""
    return await service.create_role(actor, body)


@router.patch("/roles/{key}", response_model=RoleOut, responses=ERRORS)
async def update_role(
    key: str, body: RoleUpdate, actor: CurrentActor, service: Organization
) -> RoleOut:
    """`org.roles.manage`. Not Super Admin, not a role the actor holds, nothing above them."""
    return await service.update_role(actor, key, body)


@router.get("/users", response_model=list[UserRoles], responses=ERRORS)
async def list_user_roles(actor: CurrentActor, service: Organization) -> list[UserRoles]:
    """`org.roles.assign`. Sign-in accounts and their roles."""
    return await service.users(actor)


@router.put("/users/{user_id}/roles", response_model=UserRoles, responses=ERRORS)
async def set_user_roles(
    user_id: uuid.UUID, body: UserRolesUpdate, actor: CurrentActor, service: Organization
) -> UserRoles:
    """`org.roles.assign`. Never one's own roles; only roles within the actor's authority."""
    return await service.set_user_roles(actor, user_id, body)


@router.get("/org-audit", response_model=list[OrgAuditEntry], responses=ERRORS)
async def org_audit(
    actor: CurrentActor,
    service: Organization,
    action: Annotated[str | None, Query(max_length=60)] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> list[OrgAuditEntry]:
    """`org.audit.view`. Departments, designations, reporting, roles; newest first."""
    return await service.audit(actor, limit=limit, action=action)


# ==================================================================== Team & Roles: accounts


def get_accounts_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    clock: Annotated[Clock, Depends(get_clock)],
    settings: Annotated[Settings, Depends(get_app_settings)],
    identity: Annotated[IdentityProvider, Depends(get_identity_provider)],
) -> AccountsService:
    return AccountsService(session, clock=clock, settings=settings, identity=identity)


Accounts = Annotated[AccountsService, Depends(get_accounts_service)]


@router.get("/accounts", response_model=AccountsOverview, responses=ERRORS)
async def list_accounts(actor: CurrentActor, service: Accounts) -> AccountsOverview:
    """Sign-in accounts with roles, status and workload (Team & Roles)."""
    return await service.overview(actor)


@router.post(
    "/accounts/invite",
    status_code=status.HTTP_201_CREATED,
    response_model=InviteResult,
    responses=ERRORS,
)
async def invite_account(
    body: InviteRequest, actor: CurrentActor, service: Accounts
) -> InviteResult:
    """`users.manage`. Creates the account and returns a one-time password-setup link."""
    return await service.invite(actor, body)


@router.post("/accounts/{user_id}/deactivate", response_model=Account, responses=ERRORS)
async def deactivate_account(user_id: uuid.UUID, actor: CurrentActor, service: Accounts) -> Account:
    """`users.manage`. Signs the person out everywhere; never yourself or above you."""
    return await service.set_active(actor, user_id, active=False)


@router.post("/accounts/{user_id}/reactivate", response_model=Account, responses=ERRORS)
async def reactivate_account(user_id: uuid.UUID, actor: CurrentActor, service: Accounts) -> Account:
    return await service.set_active(actor, user_id, active=True)
