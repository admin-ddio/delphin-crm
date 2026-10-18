# 0006. Two-layer authorisation: permissions plus record-level scopes

- Status: accepted
- Date: 2026-10-16

## Context and problem statement

The pilot (`docs/permissions.md`) authorises in two layers: (1) permission strings granted through roles,
with `*` for Super Admin; (2) record-level scopes applied to every list query and mutation. The pilot
had a real bug where an `OR` filter was dict-merged into a scope and widened access.

## Decision outcome

Port the model, not reinvent it:

- `authz/permissions.py`: catalogue constants and default roles (configuration, seeded by
  `make seed-config`).
- `authz/dependencies.py`: `get_actor`, `require_permission`, `require_any`; permission strings are
  validated when the route is defined.
- `authz/scopes.py`: a `Scope` returns one boolean clause; `apply_scope` ANDs caller filters with it.
  Filters can only narrow a scope. A unit test guards the composition.
- The UI hides what the actor can't do (`lib/permissions.ts`), but the API is the authority.

### Consequences

- Every module must implement a `Scope` and use `apply_scope` in every repository list or mutation query.
- Super Admin bypass is explicit (`Actor.is_super_admin`), never implied by a missing scope.
