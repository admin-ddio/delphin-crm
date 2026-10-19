# Team: parity checklist

> **Status: sign-up approvals and HR phase 1 (people core) built (2026-10-19) from the HR
> brief, pending pilot confirmation.** Every `TODO(pilot-port)` below must be filled **from the
> pilot source**, never from memory. See [docs/pilot-parity.md](../../../../docs/pilot-parity.md).

| | |
|---|---|
| Pilot sources | `services/employees.ts, services/teams.ts` (services and authz under `reference/pilot/nextjs-app/src/server/`, API routes under `src/app/api/`) |
| Pilot routes | /team, /team/employees, /team/employees/new, /team/employees/:id, /team/teams, /team/teams/:id, /team/workload |
| Backend slot | `backend/app/modules/team/` → `/api/v1/team` |
| Frontend slot | `frontend/src/features/team/` |

## Actions → REST endpoints

| Action | Method | Path | Permission | Status |
|---|---|---|---|---|
| sign-ups: list / approve / reject | GET/POST | `/api/v1/team/registrations…` | `users.approve` | built |
| employee directory | GET | `/api/v1/team/employees` | signed in | built |
| create employee | POST | `/api/v1/team/employees` | `hr.manage` | built |
| profile | GET | `/api/v1/team/employees/{id}` | signed in (sections by visibility) | built |
| edit employment / reporting manager | PATCH | `/api/v1/team/employees/{id}` | `hr.manage` | built |
| edit personal details | PATCH | `/api/v1/team/employees/{id}/personal` | the employee, or `hr.manage` | built |
| employment history | GET | `/api/v1/team/employees/{id}/history` | employment visibility | built |
| dotted lines add / end | POST/DELETE | `…/{id}/dotted-lines` | `hr.manage` | built |
| unlinked accounts | GET | `/api/v1/team/employees/user-options` | `hr.manage` | built |
| departments list / create / edit (head, deactivate) | GET/POST/PATCH | `/api/v1/team/departments…` | read: signed in; write: `hr.manage` | built |
| designations list / create / edit | GET/POST/PATCH | `/api/v1/team/designations…` | read: signed in; write: `hr.manage` | built |
| teams, workload | | `/team/teams/:id`, `/team/workload` | | not-started |

## Business rules (HR brief)

- [x] Six departments exist (migration `0008_people`); only the SEO Team has a head (Vinay Kumar, set by `scripts/seed_hr.py` in development); the others are "To be assigned"
- [x] Employee IDs DD-0001… from the transactional counter, never reused
- [x] An employee links to at most one existing sign-in account; accounts are never duplicated
- [x] One direct manager at a time (history kept as ended reporting lines); no self-reporting, no loops; any number of dotted lines
- [x] Leave approver is configurable per employee; when unset, the direct manager applies
- [x] A department with current employees can't be deactivated; inactive departments/designations can't be assigned
- [x] Exits are refused as a status edit (offboarding arrives in phase 5)
- [x] Every change audited; employment changes also in the employee's history; personal-detail changes record field names only, never values

## Record-level visibility

- Directory and overview: everyone signed in.
- Employment section, history: the employee, anyone above them in the direct chain, dotted-line managers, their department head, `hr.view_all`.
- Personal section: the employee and `hr.personal.view`.
- New role `hr_admin` (HR / Operations Admin): `hr.manage`, `hr.view_all`, `hr.personal.view`.

## Entities (interim, migration `0008_people`)

- `departments`, `designations`, `employees`, `employee_personal` (1:1, restricted), `reporting_lines` (direct/dotted with dates), `employment_events`
- TODO(pilot-port): reconcile with schema.prisma

## Next HR phases

2. Onboarding templates, tasks, documents (private storage). 3. Leave. 4. Attendance (daily check-in/out, alternate Saturdays off). 5. Probation, performance, assets & access, offboarding. 6. Announcements & policy acknowledgements, notifications, HR dashboards, reports & exports.
