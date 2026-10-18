# Onboarding: parity checklist

> **Status: not started.** The pilot was not present in `reference/pilot/` when this slot
> was scaffolded. Every `TODO(pilot-port)` below must be filled **from the pilot source**,
> never from memory. See [docs/pilot-parity.md](../../../../docs/pilot-parity.md).

| | |
|---|---|
| Pilot sources | `services/onboarding.ts` (services and authz under `reference/pilot/nextjs-app/src/server/`, API routes under `src/app/api/`) |
| Pilot routes | /onboarding, public /q/:token |
| Backend slot | `backend/app/modules/onboarding/` → `/api/v1/onboarding` |
| Frontend slot | `frontend/src/features/onboarding/` |

## Actions → REST endpoints

| Pilot Server Action | Method | Path | Permission | Status |
|---|---|---|---|---|
| TODO(pilot-port): one row per export in `src/app/actions/*` for this domain | | `/api/v1/onboarding…` | | not-started |

## Business rules

- [ ] 13 onboarding steps with server-side gating
- [ ] Review requires steps 1–10
- [ ] Completion requires all access verified and KPIs client-confirmed
- [ ] Public questionnaire /q/:token is unauthenticated and token-scoped

Quote each rule from `reference/pilot/nextjs-app/docs/*.md` with a file reference when porting.

## Entities to port (schema.prisma → `models.py` + Alembic revision)

- TODO(pilot-port): models, enums, unique/partial indexes and FKs for this domain

## Pilot tests to port

- TODO(pilot-port): `reference/pilot/nextjs-app/tests/**` cases touching this domain

## Record-level scope

- TODO(pilot-port): scope rules from `src/server/authz/*` → a `Scope` implementation used by every query
