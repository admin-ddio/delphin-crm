# Clients: parity checklist

> **Status: core built (2026-10-18) from the clickable demo, pending pilot confirmation.** The pilot was not present in `reference/pilot/` when this slot
> was scaffolded. Every `TODO(pilot-port)` below must be filled **from the pilot source**,
> never from memory. See [docs/pilot-parity.md](../../../../docs/pilot-parity.md).

| | |
|---|---|
| Pilot sources | `services/clients.ts` (services and authz under `reference/pilot/nextjs-app/src/server/`, API routes under `src/app/api/`) |
| Pilot routes | /clients, /clients/new, /clients/:id + tabs edit, contacts, onboarding, projects, tasks, services, kpis, meetings, communications, documents, approvals, billing, activity |
| Backend slot | `backend/app/modules/clients/` → `/api/v1/clients` |
| Frontend slot | `frontend/src/features/clients/` |

## Actions → REST endpoints

| Pilot Server Action | Method | Path | Permission | Status |
|---|---|---|---|---|
| list (search, status filter, sort, pages) | GET | `/api/v1/clients` | signed in (scoped) | built |
| create | POST | `/api/v1/clients` | `clients.create` | built |
| view | GET | `/api/v1/clients/{id}` | signed in (scoped; 404 outside scope) | built |
| edit | PATCH | `/api/v1/clients/{id}` | own Account Manager or Super Admin | built |
| activity | GET | `/api/v1/clients/{id}/activity` | signed in (scoped) | built |
| Account Manager options | GET | `/api/v1/clients/account-managers` | `clients.create` or `clients.update` | built |
| contacts, team, delete/archive | | | | not-started |
| TODO(pilot-port): compare with `src/app/actions/*` client exports | | | | |

## Business rules

- [x] Duplicate client detection: same normalised domain = hard block (DB-enforced, race-safe); similar normalised name = warning overridable with "This is a different business" (demo rules, `rules.py`)
- [ ] Financial fields are stripped from responses without the finance permission (shared with finance)

Quote each rule from `reference/pilot/nextjs-app/docs/*.md` with a file reference when porting.

## Entities to port (schema.prisma → `models.py` + Alembic revision)

- TODO(pilot-port): models, enums, unique/partial indexes and FKs for this domain

## Pilot tests to port

- TODO(pilot-port): `reference/pilot/nextjs-app/tests/**` cases touching this domain

## Record-level scope

- TODO(pilot-port): scope rules from `src/server/authz/*` → a `Scope` implementation used by every query

## Built from the clickable demo (2026-10-18)

- [x] Codes `CL-0001…` from the transactional counter
- [x] Lifecycle status `contract_pending → onboarding → active` (moved by onboarding when ported)
- [x] Scope: `clients.view_all` (AM, PM, Finance, Super Admin) sees all; others only clients they
      manage. TODO(pilot-port): add "clients they work on" (team / assigned tasks)
- [x] Only the client's own Account Manager (or Super Admin) edits; hidden clients answer 404
- [x] Every create/edit audited with field changes and logged to the client activity timeline
- [ ] Contacts tab, internal team, onboarding progress column: with the onboarding/contacts ports
