# Team: parity checklist

> **Status: sign-up approvals, HR phase 1 (people core, 2026-10-19) and Organization &
> Role Settings (2026-10-20) built from the HR and Organization Structure briefs, pending
> pilot confirmation.** Every `TODO(pilot-port)` below must be filled **from the pilot
> source**, never from memory. See [docs/pilot-parity.md](../../../../docs/pilot-parity.md).

| | |
|---|---|
| Pilot sources | `services/employees.ts, services/teams.ts` (services and authz under `reference/pilot/nextjs-app/src/server/`, API routes under `src/app/api/`) |
| Pilot routes | /team, /team/employees, /team/employees/new, /team/employees/:id, /team/teams, /team/teams/:id, /team/workload |
| Backend slot | `backend/app/modules/team/` → `/api/v1/team` (services in `service/`: `registrations`, `people`, `org`, `structure`) |
| Frontend slot | `frontend/src/features/team/` (`/team/teams` = Organization & Role Settings) |

## Actions → REST endpoints

| Action | Method | Path | Permission | Status |
|---|---|---|---|---|
| sign-ups: list / approve / reject | GET/POST | `/api/v1/team/registrations…` | `users.approve` | built |
| employee directory | GET | `/api/v1/team/employees` | `org.directory.view` | built |
| create employee | POST | `/api/v1/team/employees` | `hr.manage` (+ `org.reporting.manage` for department, designation, manager) | built |
| profile | GET | `/api/v1/team/employees/{id}` | `org.directory.view` (sections by visibility) | built |
| edit HR record | PATCH | `/api/v1/team/employees/{id}` | `hr.manage` | built |
| edit placement (department, designation, executive, direct manager) | PATCH | `/api/v1/team/employees/{id}` | `org.reporting.manage` | built |
| edit personal details | PATCH | `/api/v1/team/employees/{id}/personal` | the employee, or `hr.manage` | built |
| employment history | GET | `/api/v1/team/employees/{id}/history` | employment visibility | built |
| reporting relationships (lines, effective, history) | GET | `…/{id}/reporting` | `org.view` | built |
| preview a reporting change (errors + chart) | POST | `…/{id}/reporting/preview` | `org.reporting.manage` / `org.projects.assign` | built |
| save a reporting change (effective date) | PUT | `…/{id}/reporting` | `org.reporting.manage`; `org.projects.assign` for PM lines only | built |
| project options for PM lines | GET | `/api/v1/team/project-options` | as above | built |
| org chart (executive + delivery) | GET | `/api/v1/team/org-chart` | `org.view` | built |
| departments list / create / edit (owners, head, delivery PM, (de)activate) | GET/POST/PATCH | `/api/v1/team/departments…` | read: signed in; write: `org.departments.manage` | built |
| designations list / create / edit | GET/POST/PATCH | `/api/v1/team/designations…` | read: signed in; write: `org.designations.manage` | built |
| roles: matrix / create / edit | GET/POST/PATCH | `/api/v1/team/roles…` | `org.roles.manage` (read also `org.roles.assign`) | built |
| users' roles: list / set | GET/PUT | `/api/v1/team/users…` | `org.roles.assign` | built |
| organisation audit log | GET | `/api/v1/team/org-audit` | `org.audit.view` | built |
| unlinked accounts | GET | `/api/v1/team/employees/user-options` | `hr.manage` | built |
| Team & Roles: accounts (roles, status, workload) | GET | `/api/v1/team/accounts` | `users.manage`, `org.roles.assign`, `users.approve` or `org.team.view` | built |
| invite a person (setup link) | POST | `/api/v1/team/accounts/invite` | `users.manage` (roles within authority) | built |
| deactivate / reactivate | POST | `/api/v1/team/accounts/{id}/deactivate`, `…/reactivate` | `users.manage` (not yourself, not above you) | built |
| teams, workload | | `/team/teams/:id`, `/team/workload` | | not-started |

## Business rules (HR and Organization Structure briefs)

- [x] Nine departments with purposes (migration `0010_org_structure`: Content Writers Team → Content Team, Development Team → Web Development Team, + Performance Marketing, Application Development, Project Management); the brief's suggested designations per department; company-level founder titles
- [x] Founders flagged `is_executive` (shown side by side; nobody placed under another automatically)
- [x] Seven independent relationship types with effective dates; ended lines kept (`ends_on`, `ended_by`); one open line per single-valued kind; several functional / project lines, never duplicated
- [x] Department defaults: owners → functional manager(s) and escalation; delivery manager → project manager; head → department head; leave approver / reviewer → direct manager, else functional
- [x] Design has two owners (dual functional reporting) without duplicated employees
- [x] Project Manager lines may point at a project; they never change department or functional manager
- [x] No self-reporting, no former employees as managers, no loops through direct + functional (inherited included), checked on reporting, department moves and owner changes
- [x] Preview before save; effective date not in the future, not before an ended line started
- [x] Designations never grant permissions; roles do
- [x] Role authority: only permissions you hold can be granted; never `*`; Super Admin, roles you hold and roles above you are read-only; nobody changes their own roles; users holding roles above you can't be changed
- [x] Organization Admin (`org_admin`) has only `org.*` (no HR records, clients, projects, sign-ups); starts with nobody assigned; HR / Operations Admin keeps employee records only
- [x] Role edits apply on the next request (permissions are recomputed per request)
- [x] Employee IDs DD-0001… never reused; an employee links to at most one sign-in account
- [x] A department with current employees can't be deactivated; inactive departments/designations can't be assigned
- [x] Exits are refused as a status edit (offboarding arrives in phase 5)
- [x] Every change audited (`department.*`, `designation.*`, `reporting.changed`, `role.*`, `user.roles_changed`, `employee.placement_changed`); employment changes also in the employee's history; personal-detail changes record field names only
- [ ] Future-dated reporting changes (scheduled) — not supported yet; the effective date is today or earlier

- [x] Team & Roles hub (2026-10-28): invitations return a one-time setup link (e-mail not configured); deactivation revokes all sessions; the permission matrix stays in Organization & Roles

## Record-level visibility

- Directory and overview: `org.directory.view` (every default role).
- Employment section, history: the employee, their direct chain, anyone holding a relationship over them (explicit or inherited), `hr.view_all`.
- Personal section: the employee and `hr.personal.view`.
- Project names next to PM assignments: `projects.view_all`, `org.projects.assign`, `org.reporting.manage`, or the project's manager; others see "Restricted project".

## Entities (interim, migrations `0008_people`, `0010_org_structure`)

- `departments` (+ `delivery_manager_id`), `department_owners`, `designations` (+ `department_id`, unique per department), `employees` (+ `is_executive`; `leave_approver_id` moved into reporting lines), `employee_personal`, `reporting_lines` (7 kinds, `project_id`, `ended_by_id`), `employment_events`
- TODO(pilot-port): reconcile with schema.prisma

## Next HR phases

2. Onboarding templates, tasks, documents (private storage). 3. Leave (approver = effective `leave_approver`). 4. Attendance (daily check-in/out, alternate Saturdays off). 5. Probation, performance (reviewer = effective `performance_reviewer`), assets & access, offboarding. 6. Announcements & policy acknowledgements, notifications, HR dashboards, reports & exports.
