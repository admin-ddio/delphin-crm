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
from app.core.errors import AUTH_ERROR_RESPONSES, ErrorEnvelope
from app.db.session import get_session
from app.modules.team.schemas import (
    ApproveRegistrationRequest,
    DepartmentIn,
    DepartmentOut,
    DepartmentUpdate,
    DesignationIn,
    DesignationOut,
    DesignationUpdate,
    DottedLineIn,
    EmployeeCreate,
    EmployeeDetail,
    EmployeeListItem,
    EmployeeStatus,
    EmployeeUpdate,
    EmploymentEventOut,
    PendingRegistration,
    PersonalUpdate,
    UserOption,
)
from app.modules.team.service import PeopleService, TeamService
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
    status_filter: Annotated[EmployeeStatus | None, Query(alias="status")] = None,
    include_exited: Annotated[bool, Query()] = False,
) -> list[EmployeeListItem]:
    """The employee directory (everyone signed in), alphabetical."""
    return await service.list_employees(
        actor, q=q, department_id=department_id, status=status_filter, include_exited=include_exited
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
    """`hr.manage`. Codes are DD-0001, DD-0002…"""
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
    """`hr.manage`. Partial; `manager_id` replaces the direct manager (history kept)."""
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


@router.post(
    "/employees/{employee_id}/dotted-lines", response_model=EmployeeDetail, responses=ERRORS
)
async def add_dotted_line(
    employee_id: uuid.UUID, body: DottedLineIn, actor: CurrentActor, service: People
) -> EmployeeDetail:
    return await service.add_dotted_line(actor, employee_id, body)


@router.delete(
    "/employees/{employee_id}/dotted-lines/{line_id}",
    response_model=EmployeeDetail,
    responses=ERRORS,
)
async def end_dotted_line(
    employee_id: uuid.UUID, line_id: uuid.UUID, actor: CurrentActor, service: People
) -> EmployeeDetail:
    return await service.end_dotted_line(actor, employee_id, line_id)


@router.get("/departments", response_model=list[DepartmentOut], responses=AUTH_ERROR_RESPONSES)
async def list_departments(actor: CurrentActor, service: People) -> list[DepartmentOut]:
    """Every department with its head and current headcount."""
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
    """Rename, set the head, or (de)activate (only when it has no employees)."""
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
