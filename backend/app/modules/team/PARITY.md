# Team: parity checklist

> **Status: not started.** The pilot was not present in `reference/pilot/` when this slot
> was scaffolded. Every `TODO(pilot-port)` below must be filled **from the pilot source**,
> never from memory. See [docs/pilot-parity.md](../../../../docs/pilot-parity.md).

| | |
|---|---|
| Pilot sources | `services/employees.ts, services/teams.ts` (services and authz under `reference/pilot/nextjs-app/src/server/`, API routes under `src/app/api/`) |
| Pilot routes | /team, /team/employees, /team/employees/new, /team/employees/:id, /team/teams, /team/teams/:id, /team/workload |
| Backend slot | `backend/app/modules/team/` → `/api/v1/team` |
| Frontend slot | `frontend/src/features/team/` |

## Actions → REST endpoints

| Pilot Server Action | Method | Path | Permission | Status |
|---|---|---|---|---|
| TODO(pilot-port): one row per export in `src/app/actions/*` for this domain | | `/api/v1/team…` | | not-started |

## Business rules

- [ ] TODO(pilot-port): list from reference/pilot/nextjs-app/docs/modules.md

Quote each rule from `reference/pilot/nextjs-app/docs/*.md` with a file reference when porting.

## Entities to port (schema.prisma → `models.py` + Alembic revision)

- TODO(pilot-port): models, enums, unique/partial indexes and FKs for this domain

## Pilot tests to port

- TODO(pilot-port): `reference/pilot/nextjs-app/tests/**` cases touching this domain

## Record-level scope

- TODO(pilot-port): scope rules from `src/server/authz/*` → a `Scope` implementation used by every query

## Built ahead of the pilot port: sign-up approvals (2026-10-17)

| Action | Method | Path | Permission | Status |
|---|---|---|---|---|
| list pending sign-ups | GET | `/api/v1/team/registrations` | `users.approve` | built |
| approve with a role | POST | `/api/v1/team/registrations/{id}/approve` | `users.approve` | built |
| reject (deletes app user + Firebase login) | POST | `/api/v1/team/registrations/{id}/reject` | `users.approve` | built |

The `/team` page shows a "Pending sign-ups" panel to approvers; the rest of Team & roles (people
list, capability matrix) is still a placeholder.
