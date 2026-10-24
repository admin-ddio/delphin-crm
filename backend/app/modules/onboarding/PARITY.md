# Onboarding: parity checklist

> **Status: built (2026-10-19) from the clickable demo, pending pilot confirmation.** The pilot was not present in `reference/pilot/` when this slot
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
| board | GET | `/api/v1/onboarding` | signed in (client scope) | built |
| detail (13 steps, all sections) | GET | `/api/v1/onboarding/clients/{id}` | client scope | built |
| contract record / sign | POST | `…/clients/{id}/contract` | client's AM or Super Admin | built |
| send questionnaire link | POST | `…/questionnaire/send` | AM | built |
| record answers | POST | `…/questionnaire/answers` | AM | built |
| public questionnaire | GET/POST | `/api/v1/onboarding/questionnaire/{token}` | single-use token | built |
| access status | PATCH | `…/access/{key}` | AM (received…) / `onboarding.access_verify` (verify, reject) | built |
| mark all received | POST | `…/access/receive-all` | AM | built |
| KPI add / remove | POST/DELETE | `…/kpis` | AM | built |
| KPI client confirmation | POST | `…/kpis/confirm` | `onboarding.kpi_confirm` | built |
| kickoffs | POST | `…/kickoffs/{client,internal}` | AM | built |
| team add / remove / options | POST/DELETE/GET | `…/team` | AM | built |
| review, complete | POST | `…/review`, `…/complete` | AM | built |
| TODO(pilot-port): compare with `src/app/actions/*` onboarding exports | | | | |

## Business rules

- [x] 13 onboarding steps with server-side gating (`steps.py`, pure + unit-tested)
- [x] Review requires steps 1–10
- [x] Completion requires all access verified and KPIs client-confirmed (then steps 1–11); client becomes Active; workflow locked
- [x] Public questionnaire /q/:token is unauthenticated, single-use, 30 days, token stored hashed

Quote each rule from `reference/pilot/nextjs-app/docs/*.md` with a file reference when porting.

## Entities to port (schema.prisma → `models.py` + Alembic revision)

- TODO(pilot-port): models, enums, unique/partial indexes and FKs for this domain

## Pilot tests to port

- TODO(pilot-port): `reference/pilot/nextjs-app/tests/**` cases touching this domain

## Record-level scope

- TODO(pilot-port): scope rules from `src/server/authz/*` → a `Scope` implementation used by every query

## Also built (demo rules)

- [x] Access: verify/reject only after "received", by `onboarding.access_verify`; a rejection blocks onboarding
- [x] KPIs: client confirmation records who and how (email/call/meeting/WhatsApp); confirmed KPIs can't be removed
- [x] Internal kickoff step needs at least one team member; team members can then see the client
- [x] Signing the contract moves the client to "Onboarding"; completion to "Active"
- [x] Every action audited and on the client activity timeline
- [ ] Step 13 (project created / linked): with the Projects module
- [ ] E-mailing the questionnaire link: the AM copies it (no e-mail delivery yet)
