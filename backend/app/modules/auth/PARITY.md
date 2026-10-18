# Auth: parity checklist

> **Status: built (2026-10-16), Firebase Auth identity (ADR-0009), pending pilot confirmation.** Implemented from the scaffold brief and the
> clickable demo because the pilot source was not present. Re-check every rule below against
> `services/auth.ts` and `server/auth/*` when it arrives. Originally: the pilot was not present in `reference/pilot/` when this slot
> was scaffolded. Every `TODO(pilot-port)` below must be filled **from the pilot source**,
> never from memory. See [docs/pilot-parity.md](../../../../docs/pilot-parity.md).

| | |
|---|---|
| Pilot sources | `services/auth.ts, server/auth/*` (services and authz under `reference/pilot/nextjs-app/src/server/`, API routes under `src/app/api/`) |
| Pilot routes | /login, /forgot-password, /reset-password/:token, /activate/:token, /account |
| Backend slot | `backend/app/modules/auth/` → `/api/v1/auth` |
| Frontend slot | `frontend/src/features/auth/` |

## Actions → REST endpoints

| Pilot Server Action | Method | Path | Permission | Status |
|---|---|---|---|---|
| sign in (Firebase ID token → app session) | POST | `/api/v1/auth/session` | public (verified Firebase identity, invited + active) | built |
| logout | POST | `/api/v1/auth/logout` | signed in | built |
| current user | GET | `/api/v1/auth/me` | signed in | built |
| sign out other sessions | POST | `/api/v1/auth/sessions/revoke-others` | signed in | built |
| forgot / reset password, verify e-mail | — | Firebase JS SDK + `/auth/action` page | public | built (Firebase) |
| invite user | — | `AuthService.invite` (script now; Team module UI later) | super admin | built |
| TODO(pilot-port): compare with `src/app/actions/*` auth exports | | | | |

## Business rules

- [x] Failed-attempt throttling: delegated to Firebase Auth (ADR-0009). TODO(pilot-port): compare with the pilot rule "count failed attempts per account only"
- [x] Sessions: opaque token in HttpOnly cookie, SHA-256 at rest (ADR-0003), 12 h TTL
- [x] Forbidden/unauthorised errors are redacted in production; one generic sign-in error

Quote each rule from `reference/pilot/nextjs-app/docs/*.md` with a file reference when porting.

## Entities to port (schema.prisma → `models.py` + Alembic revision)

- TODO(pilot-port): models, enums, unique/partial indexes and FKs for this domain

## Pilot tests to port

- TODO(pilot-port): `reference/pilot/nextjs-app/tests/**` cases touching this domain

## Record-level scope

- TODO(pilot-port): scope rules from `src/server/authz/*` → a `Scope` implementation used by every query
- [x] E-mail must be verified (Firebase) before an app session is issued
- [x] Only invited, active users get a session; a different Firebase uid can't take over a linked e-mail

## Self sign-up (added on request, 2026-10-17; NOT a pilot feature)

- `/signup` (linked from the login page: "Don't have an account? Sign up") creates the Firebase
  login, sends the verification e-mail and calls `POST /api/v1/auth/register`.
- The app user is created **pending** (`approved_at` NULL, no role). Sign-in answers
  `403 pending_approval` until an approver acts; e-mail verification is still required.
- Registration is idempotent for the same Firebase account; an e-mail that already belongs to
  an app user is refused (409).
- Approval and rejection live in the team module (`/api/v1/team/registrations`, permission
  `users.approve`). Invitations count as approved. Migration `0003_users_approval`.
- TODO(pilot-port): the pilot is invite-only per the brief; confirm the product owner wants
  self sign-up kept when the pilot is compared.
