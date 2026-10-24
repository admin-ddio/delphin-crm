"""The organisation in memory and how reporting relationships resolve.

Explicit reporting lines win; otherwise department defaults apply:
- functional manager(s)   ← the department's executive owners (Design has two);
- project manager         ← the department's delivery manager;
- department head         ← the department's head;
- executive escalation    ← the department's executive owners;
- leave approver and performance reviewer ← direct manager, else functional manager(s).
Nobody inherits themself. Project Manager lines never replace the department or the
functional manager: each kind resolves on its own (Organization brief §5).
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field, replace
from datetime import date

from app.modules.team.models import (
    MULTI_KINDS,
    REPORTING_KINDS,
    Department,
    Designation,
    Employee,
    ReportingLine,
)
from app.modules.team.schemas import PersonRef, ProjectRef, Relation

KIND_LABELS: dict[str, str] = {
    "direct_manager": "Direct manager",
    "functional_manager": "Functional manager",
    "project_manager": "Project manager",
    "department_head": "Department head",
    "leave_approver": "Leave approver",
    "performance_reviewer": "Performance reviewer",
    "executive_escalation": "Executive escalation",
}
SINGLE_KINDS = frozenset(REPORTING_KINDS) - MULTI_KINDS


@dataclass(frozen=True, slots=True)
class Resolved:
    kind: str
    manager_id: uuid.UUID
    source: str
    project_id: uuid.UUID | None = None
    starts_on: date | None = None


@dataclass
class Org:
    """The whole organisation (small agency: a few hundred rows at most)."""

    employees: dict[uuid.UUID, Employee]
    departments: dict[uuid.UUID, Department]
    designations: dict[uuid.UUID, Designation]
    #: Open (active) lines only.
    lines: list[ReportingLine]
    #: department id → executive owner employee ids.
    owners: dict[uuid.UUID, list[uuid.UUID]]
    #: Pending department moves (employee id → department id) for previews and checks.
    moves: dict[uuid.UUID, uuid.UUID | None] = field(default_factory=dict)
    by_employee: dict[uuid.UUID, list[ReportingLine]] = field(init=False)
    manager_of: dict[uuid.UUID, uuid.UUID] = field(init=False)
    reports: dict[uuid.UUID, list[uuid.UUID]] = field(init=False)

    def __post_init__(self) -> None:
        self.by_employee = defaultdict(list)
        self.manager_of = {}
        self.reports = defaultdict(list)
        for line in self.lines:
            self.by_employee[line.employee_id].append(line)
            if line.kind == "direct_manager":
                self.manager_of[line.employee_id] = line.manager_id
                self.reports[line.manager_id].append(line.employee_id)

    # ------------------------------------------------------------ variants

    def with_lines(self, employee_id: uuid.UUID, lines: list[ReportingLine]) -> Org:
        """A copy where the employee's open lines are replaced."""
        others = [ln for ln in self.lines if ln.employee_id != employee_id]
        return replace(self, lines=others + lines)

    def with_owners(self, department_id: uuid.UUID, owner_ids: list[uuid.UUID]) -> Org:
        return replace(self, owners={**self.owners, department_id: list(owner_ids)})

    def with_move(self, employee_id: uuid.UUID, department_id: uuid.UUID | None) -> Org:
        return replace(self, moves={**self.moves, employee_id: department_id})

    # ------------------------------------------------------------ lookups

    def by_user(self, user_id: uuid.UUID) -> Employee | None:
        return next((e for e in self.employees.values() if e.user_id == user_id), None)

    def department_id_of(self, employee: Employee) -> uuid.UUID | None:
        if employee.id in self.moves:
            return self.moves[employee.id]
        return employee.department_id

    def department_of(self, employee: Employee) -> Department | None:
        department_id = self.department_id_of(employee)
        return self.departments.get(department_id) if department_id else None

    def person(self, employee_id: uuid.UUID | None) -> PersonRef | None:
        employee = self.employees.get(employee_id) if employee_id else None
        if employee is None:
            return None
        return PersonRef(id=employee.id, code=employee.code, full_name=employee.full_name)

    def people(self, ids: list[uuid.UUID]) -> list[PersonRef]:
        return [p for p in (self.person(i) for i in ids) if p is not None]

    def name(self, employee_id: uuid.UUID | None) -> str:
        employee = self.employees.get(employee_id) if employee_id else None
        return employee.full_name if employee else "—"

    def active(self, employee_id: uuid.UUID | None) -> bool:
        employee = self.employees.get(employee_id) if employee_id else None
        return employee is not None and employee.status != "exited"

    # ------------------------------------------------------------ resolution

    def explicit(self, employee_id: uuid.UUID, kind: str) -> list[ReportingLine]:
        return [ln for ln in self.by_employee.get(employee_id, []) if ln.kind == kind]

    def resolve(self, employee: Employee) -> list[Resolved]:
        """Every relationship that applies to the employee, in REPORTING_KINDS order."""
        department = self.department_of(employee)
        owners = [
            i
            for i in (self.owners.get(department.id, []) if department else [])
            if i != employee.id and self.active(i)
        ]

        def explicit(kind: str) -> list[Resolved]:
            return [
                Resolved(kind, ln.manager_id, "explicit", ln.project_id, ln.starts_on)
                for ln in self.explicit(employee.id, kind)
            ]

        def inherited(kind: str, ids: list[uuid.UUID], source: str) -> list[Resolved]:
            return [Resolved(kind, i, source) for i in ids if i != employee.id and self.active(i)]

        result: dict[str, list[Resolved]] = {}
        result["direct_manager"] = explicit("direct_manager")
        result["functional_manager"] = explicit("functional_manager") or inherited(
            "functional_manager", owners, "department"
        )
        pm = department.delivery_manager_id if department else None
        result["project_manager"] = explicit("project_manager") or inherited(
            "project_manager", [pm] if pm else [], "department"
        )
        head = department.head_id if department else None
        result["department_head"] = explicit("department_head") or inherited(
            "department_head", [head] if head else [], "department"
        )
        direct = [r.manager_id for r in result["direct_manager"]]
        functional = [r.manager_id for r in result["functional_manager"]]
        for kind in ("leave_approver", "performance_reviewer"):
            result[kind] = (
                explicit(kind)
                or inherited(kind, direct, "direct_manager")
                or inherited(kind, functional, "functional_manager")
            )
        result["executive_escalation"] = explicit("executive_escalation") or inherited(
            "executive_escalation", owners, "department"
        )
        return [r for kind in REPORTING_KINDS for r in result[kind]]

    def resolve_kind(self, employee: Employee, kind: str) -> list[Resolved]:
        return [r for r in self.resolve(employee) if r.kind == kind]

    def relations(
        self, employee: Employee, projects: dict[uuid.UUID, ProjectRef] | None = None
    ) -> list[Relation]:
        result = []
        for r in self.resolve(employee):
            manager = self.person(r.manager_id)
            if manager is None:
                continue
            result.append(
                Relation(
                    kind=r.kind,  # type: ignore[arg-type]  # DB check constraint
                    kind_label=KIND_LABELS[r.kind],
                    manager=manager,
                    source=r.source,  # type: ignore[arg-type]
                    project=project_ref(r.project_id, projects),
                    starts_on=r.starts_on,
                )
            )
        return result

    # ------------------------------------------------------------ hierarchy

    def chain(self, employee_id: uuid.UUID) -> list[uuid.UUID]:
        """Direct managers upward (loop-safe)."""
        seen: list[uuid.UUID] = []
        current = self.manager_of.get(employee_id)
        while current is not None and current not in seen:
            seen.append(current)
            current = self.manager_of.get(current)
        return seen

    def above(self, viewer_id: uuid.UUID, employee: Employee) -> bool:
        """The viewer is in the direct chain or holds any relationship over the employee."""
        if viewer_id in self.chain(employee.id):
            return True
        return any(r.manager_id == viewer_id for r in self.resolve(employee))

    def edges(self, employee: Employee) -> set[uuid.UUID]:
        """Line-management edges checked for loops: direct and functional managers."""
        return {
            r.manager_id
            for r in self.resolve(employee)
            if r.kind in ("direct_manager", "functional_manager")
        }

    def loop_through(self, employee_id: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID] | None:
        """(manager, employee) when the employee reaches themself through their managers."""
        employee = self.employees.get(employee_id)
        if employee is None:
            return None
        for manager_id in self.edges(employee):
            stack, seen = [manager_id], set()
            while stack:
                current = stack.pop()
                if current == employee_id:
                    return manager_id, employee_id
                if current in seen or current not in self.employees:
                    continue
                seen.add(current)
                stack.extend(self.edges(self.employees[current]))
        return None

    def first_loop(
        self, among: list[uuid.UUID] | None = None
    ) -> tuple[uuid.UUID, uuid.UUID] | None:
        for employee_id in among if among is not None else list(self.employees):
            found = self.loop_through(employee_id)
            if found:
                return found
        return None

    def loop_message(self, found: tuple[uuid.UUID, uuid.UUID]) -> str:
        manager_id, employee_id = found
        return (
            f"That would create a reporting loop: {self.name(manager_id)} already "
            f"reports to {self.name(employee_id)}."
        )


def project_ref(
    project_id: uuid.UUID | None, projects: dict[uuid.UUID, ProjectRef] | None
) -> ProjectRef | None:
    if project_id is None:
        return None
    if projects is not None and project_id in projects:
        return projects[project_id]
    # Hidden from this viewer (no project access): show that an assignment exists only.
    return ProjectRef(id=project_id, code=None, name="Restricted project")
