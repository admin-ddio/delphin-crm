# Approvals: parity checklist

> **Status: built (2026-10-19) from the clickable demo, pending pilot confirmation.** Every
> `TODO(pilot-port)` below must be filled **from the pilot source**, never from memory.
> See [docs/pilot-parity.md](../../../../docs/pilot-parity.md).

| | |
|---|---|
| Pilot sources | `services/approvals.ts` (services and authz under `reference/pilot/nextjs-app/src/server/`, API routes under `src/app/api/`) |
| Pilot routes | /approvals, /approvals/:id |
| Backend slot | `backend/app/modules/approvals/` → `/api/v1/approvals` |
| Frontend slot | `frontend/src/features/approvals/` (+ `ReviewPanel` in the task drawer) |

## Actions → REST endpoints

| Pilot Server Action | Method | Path | Permission | Status |
|---|---|---|---|---|
| list (`view=mine` waiting for me, `all`) | GET | `/api/v1/approvals` | project scope | built |
| submit a version for review | POST | `/api/v1/approvals/submit` | task assignee or task manager | built |
| one request | GET | `/api/v1/approvals/{id}` | project scope | built |
| approve / request changes | POST | `/api/v1/approvals/{id}/decision` | reviewer (internal); client's AM + `approvals.client_decision` (client); Super Admin | built |
| TODO(pilot-port): compare with `src/app/actions/*` approval exports | | | | |

## Business rules

- [x] No self-approval: the submitter can't decide their own version (Super Admin excepted)
- [x] A reviewer can't submit work they'd review ("You can't review your own work. Ask the PM to set another reviewer.")
- [x] Client-stage decisions need a decision-maker and a channel (e-mail, call, meeting, WhatsApp)
- [x] "Request changes" needs feedback and sends the task back to In progress
- [x] Internal approval of a task needing client approval opens the client stage on the same version; otherwise approval completes the task
- [x] Only in-progress tasks that require review/client approval can be submitted; one open request per task (partial unique index)
- [x] Cancelling a task cancels its open request; changing the reviewer moves an open internal review
- [x] Every step audited (entity `task`) and on the client activity timeline

## Entities to port (schema.prisma → `models.py` + Alembic revision)

- [x] Interim `task_versions` and `approvals` (migration `0007_approvals`). TODO(pilot-port): reconcile with schema.prisma

## Pilot tests to port

- TODO(pilot-port): `reference/pilot/nextjs-app/tests/**` cases touching this domain

## Record-level scope

- [x] An approval is visible exactly when its task's project is (`ProjectScope`). TODO(pilot-port): confirm against `src/server/authz/*`
