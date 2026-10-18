# API guidelines

- **Prefix** `/api/v1`. Resources are plural kebab-case. One router per module, tagged with the module name.
- **OpenAPI** at `/api/v1/openapi.json`, docs at `/api/docs` (disabled in production unless
  `EXPOSE_DOCS=true`). Every route has a tag, a stable `operationId` and typed responses, because
  the frontend client is generated from it (`make gen-api`).
- **Methods**: `GET` read, `POST` create/command, `PATCH` partial update, `PUT` full replace (rare),
  `DELETE` remove. Commands that are not CRUD use a verb sub-resource, e.g.
  `POST /api/v1/approvals/{id}/decisions`.
- **Lists** return `Page[T]` = `{items, total, page, page_size}`. Query: `?page=1&page_size=25`
  (max 200), filters as validated query models, `?sort=name,-created_at` against an allow-list
  (`core.pagination.parse_sort`).
- **Idempotency**: POSTs that create records accept `Idempotency-Key` (`core.idempotency.IdempotencyKey`).
- **Errors** use the single envelope (see conventions.md). Status mapping: 401 `unauthorized`,
  403 `forbidden`, 404 `not_found`, 409 `conflict`, 413 `payload_too_large`, 422 `validation_failed` /
  `business_rule_violation`, 501 `not_implemented` (scaffold stubs), 500 `internal_error`.
- **Auth**: cookie session (`delphin_session`, HttpOnly). State-changing requests carrying that cookie
  must send `X-CSRF-Token` equal to the `delphin_csrf` cookie (get one via `GET /api/v1/auth/csrf`).
- **Authorisation**: every endpoint declares `Depends(require_permission("domain.action"))` (or
  `require_any`), and the service applies record-level scope.
- **Financial fields** are removed from responses when the actor lacks the finance permission. Do
  this in the service, not the client.
- **Files** are only served via `GET /api/v1/files/{id}`, which re-checks access on every request.
