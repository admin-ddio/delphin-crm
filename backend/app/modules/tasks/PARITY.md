# Tasks: parity checklist

> **Status: basics built (2026-10-19) from the clickable demo, pending pilot confirmation.** Review
> submission, versions and approvals arrive with the approvals module. Every `TODO(pilot-port)` below
> must be filled **from the pilot source**, never from memory. See [docs/pilot-parity.md](../../../../docs/pilot-parity.md).

| | |
|---|---|
| Pilot sources | `services/tasks.ts` (services and authz under `reference/pilot/nextjs-app/src/server/`, API routes under `src/app/api/`) |
| Pilot routes | /tasks, /tasks/new, /tasks/:id |
| Backend slot | `backend/app/modules/tasks/` → `/api/v1/tasks` |
| Frontend slot | `frontend/src/features/tasks/` |

## Actions → REST endpoints

| Pilot Server Action | Method | Path | Permission | Status |
|---|---|---|---|---|
| list (`view=mine\|all`, `open_only`) | GET | `/api/v1/tasks` | project scope | built |
| create | POST | `/api/v1/tasks` | `tasks.create` + project scope | built |
| assignee options | GET | `/api/v1/tasks/assignee-options` | `tasks.create` | built |
| detail (+ permissions, next statuses) | GET | `/api/v1/tasks/{id}` | project scope | built |
| edit title / description / assignee / due | PATCH | `/api/v1/tasks/{id}` | task manager | built |
| move on the board | POST | `/api/v1/tasks/{id}/status` | assignee or task manager | built |
| submit for review, versions, decisions | | | | next module |
| TODO(pilot-port): compare with `src/app/actions/*` task exports | | | | |

## Business rules

- [x] Tasks that require review (or client approval) cannot be completed directly ("This task requires review. Submit it for review instead of completing it directly.")
- [x] Board moves: backlog ↔ ready → in progress ↔ blocked; in progress → completed; any open → cancelled; cancelled → backlog (reopen)
- [x] Review states are entered only through the review workflow; from there only cancel
- [x] Task managers (edit, reassign, cancel, reopen): Super Admin, the project's manager, Team Leads; the assignee can work the task
- [x] Overdue = due date before today and not completed/cancelled
- [x] Codes T-1, T-2… from the transactional counter; reviewer defaults to the project manager
- [x] Every change audited (entity `task`) and on the client activity timeline

Quote each rule from `reference/pilot/nextjs-app/docs/*.md` with a file reference when porting.

## Entities to port (schema.prisma → `models.py` + Alembic revision)

- [x] Interim `tasks` table (migration `0006_projects_tasks`). TODO(pilot-port): versions, approvals, reconcile with schema.prisma

## Pilot tests to port

- TODO(pilot-port): `reference/pilot/nextjs-app/tests/**` cases touching this domain

## Record-level scope

- [x] A task is visible exactly when its project is (`ProjectScope`). TODO(pilot-port): confirm against `src/server/authz/*`
