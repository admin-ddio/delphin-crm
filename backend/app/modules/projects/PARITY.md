# Projects: parity checklist

> **Status: built (2026-10-19) from the clickable demo, pending pilot confirmation.** The pilot was not present in `reference/pilot/` when this slot
> was scaffolded. Every `TODO(pilot-port)` below must be filled **from the pilot source**,
> never from memory. See [docs/pilot-parity.md](../../../../docs/pilot-parity.md).

| | |
|---|---|
| Pilot sources | `services/projects.ts` (services and authz under `reference/pilot/nextjs-app/src/server/`, API routes under `src/app/api/`) |
| Pilot routes | /projects, /projects/new, /projects/:id |
| Backend slot | `backend/app/modules/projects/` → `/api/v1/projects` |
| Frontend slot | `frontend/src/features/projects/` |

## Actions → REST endpoints

| Pilot Server Action | Method | Path | Permission | Status |
|---|---|---|---|---|
| list (with task stats; `?client_id=`) | GET | `/api/v1/projects` | project scope | built |
| create (optional template) | POST | `/api/v1/projects` | `projects.create` + client scope | built |
| clients ready for a project | GET | `/api/v1/projects/eligible-clients` | `projects.create` | built |
| manager options | GET | `/api/v1/projects/manager-options` | `projects.create` | built |
| detail + board (all tasks) | GET | `/api/v1/projects/{id}` | project scope | built |
| TODO(pilot-port): compare with `src/app/actions/*` project exports | | | | |

## Business rules

- [x] Project creation is locked until the client's onboarding completes ("Projects can only be created after client onboarding is completed.")
- [x] The client's first project completes onboarding step 13
- [x] Manager must be an active Project Manager or Super Admin
- [x] Codes PRJ-0001… from the transactional counter
- [x] "SEO onboarding & foundation" template: 5 tasks, due = start + offset + duration, assigned to the client team's first Employee, reviewed by the PM (`templates.py`)
- [x] Progress = completed ÷ non-cancelled tasks
- [x] Create audited; summary on the client activity timeline

Quote each rule from `reference/pilot/nextjs-app/docs/*.md` with a file reference when porting.

## Entities to port (schema.prisma → `models.py` + Alembic revision)

- [x] Interim `projects` table (migration `0006_projects_tasks`). TODO(pilot-port): reconcile with schema.prisma

## Pilot tests to port

- TODO(pilot-port): `reference/pilot/nextjs-app/tests/**` cases touching this domain

## Record-level scope

- [x] `ProjectScope` (demo): `projects.view_all` (AM, PM, Finance, Super Admin) sees all; others see projects they manage, whose client team they're on, or with a task assigned to them. Hidden projects are 404.
- TODO(pilot-port): confirm against `src/server/authz/*`
