# 0004. Frontend API types generated from OpenAPI

- Status: accepted
- Date: 2026-10-16

## Context and problem statement

Hand-written DTOs drift from the backend. The pilot shared types implicitly through Server Actions; the
rebuild has a real network boundary.

## Considered options

1. `openapi-typescript` + `openapi-fetch` generated from `/api/v1/openapi.json`
2. Hand-written TypeScript interfaces
3. A full client generator (orval and similar)

## Decision outcome

Option 1. `make gen-api` exports the schema without a running server (`scripts/export_openapi.py`) and
writes `frontend/src/api/schema.d.ts`. CI fails when the committed file is stale. Every backend route
has a tag and a stable `operationId` (`<tag>_<function>`).

### Consequences

- Types only, with no generated runtime code to review. TanStack Query hooks are written per module in
  `features/<slot>/api.ts`.
- Backend schema changes show up as TypeScript errors in the same PR.
