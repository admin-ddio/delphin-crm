# Conventions

## Naming

| Thing | Convention | Example |
|---|---|---|
| Module slot | lower-case, same on both sides | `clients`, `backend/app/modules/clients`, `frontend/src/features/clients` |
| Tables | plural `snake_case` | `user_roles`, `audit_log` |
| Constraints | naming convention on `Base.metadata` | `pk_users`, `fk_sessions_user_id_users`, `uq_roles_key`, `ix_…`, `ck_auth_tokens_purpose` |
| REST resources | plural kebab-case under `/api/v1` | `/api/v1/client-services` |
| operationId | `<tag>_<function>` (auto) | `clients_list_clients` |
| Permissions | `domain.action` (lower-case, dots) | `clients.create` |
| Human codes | counters table | `CL-0001`, `PRJ-0001`, `INV-2026-0001` |

## Layering

`router → service → repository → models`, one direction, enforced by import-linter.

- **Routers** handle HTTP only: parse, call one service function, return a schema.
- **Services** hold business rules and authorisation decisions. They take `session`, `actor` and
  `clock` as arguments and never commit.
- **Repositories** hold queries. Every list query goes through `authz.scopes.apply_scope`.
- **Models** are SQLAlchemy only.

## Error envelope

Every error response, everywhere:

```json
{"error": {"code": "forbidden", "message": "…", "details": {}, "request_id": "…"}}
```

Raise domain exceptions from `app.core.errors` (`NotFound`, `Forbidden`, `Conflict`,
`ValidationFailed`, `BusinessRuleViolation`); never raise `HTTPException` in services.

## Time, money, IDs

- All timestamps are `timestamptz` in UTC. Get "now" from the injected `Clock`.
- Money is `NUMERIC(14,2)` + ISO currency (`app.db.types.Money`, `CurrencyCode`), never float.
- Primary keys are UUIDs; human-facing codes come from `platform.system.counters`.

## Frontend

- Port pilot JSX and class strings verbatim. Never restyle. Use `cn()` for conditional classes.
- All API access goes through `lib/api-client.ts` + TanStack Query; `fetch` is lint-banned elsewhere.
- Types come from the generated `api/schema.d.ts`. No hand-written DTOs.
- Copy matches the pilot exactly, including British spelling ("Organisation", "Authorisation").

## Commits

Conventional commits: `feat(clients): …`, `fix(authz): …`, `chore(repo): …`, `docs: …`, `test: …`.
