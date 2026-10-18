# Documents: parity checklist

> **Status: not started.** The pilot was not present in `reference/pilot/` when this slot
> was scaffolded. Every `TODO(pilot-port)` below must be filled **from the pilot source**,
> never from memory. See [docs/pilot-parity.md](../../../../docs/pilot-parity.md).

| | |
|---|---|
| Pilot sources | `services/documents.ts, api/files` (services and authz under `reference/pilot/nextjs-app/src/server/`, API routes under `src/app/api/`) |
| Pilot routes | /documents (+ GET /api/v1/files/:id) |
| Backend slot | `backend/app/modules/documents/` → `/api/v1/documents` |
| Frontend slot | `frontend/src/features/documents/` |

## Actions → REST endpoints

| Pilot Server Action | Method | Path | Permission | Status |
|---|---|---|---|---|
| TODO(pilot-port): one row per export in `src/app/actions/*` for this domain | | `/api/v1/documents…` | | not-started |

## Business rules

- [ ] Restricted documents are hidden from actors without access
- [ ] GET /api/v1/files/:id re-checks access on every request (no public file URLs)

Quote each rule from `reference/pilot/nextjs-app/docs/*.md` with a file reference when porting.

## Entities to port (schema.prisma → `models.py` + Alembic revision)

- TODO(pilot-port): models, enums, unique/partial indexes and FKs for this domain

## Pilot tests to port

- TODO(pilot-port): `reference/pilot/nextjs-app/tests/**` cases touching this domain

## Record-level scope

- TODO(pilot-port): scope rules from `src/server/authz/*` → a `Scope` implementation used by every query
