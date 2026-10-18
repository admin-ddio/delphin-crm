# 0007. Append-only audit log enforced by a database trigger

- Status: accepted
- Date: 2026-10-16

## Context and problem statement

Audit history must be tamper-evident even against application bugs or direct SQL. The pilot enforces
this with a PostgreSQL trigger in its migrations.

## Decision outcome

- `audit_log` has `BEFORE UPDATE OR DELETE` (per row) and `BEFORE TRUNCATE` (per statement) triggers that
  raise `insufficient_privilege` (migration `0001_platform_core`).
- `actor_user_id` has no foreign key, so user deletion can never require updating audit rows.
- `platform/audit/service.py` redacts secret-looking keys before writing.
- Downgrading `0001` drops the table; that is refused in production unless
  `ALLOW_AUDIT_LOG_DOWNGRADE=true` is set.

### Consequences

- Corrections are new entries, never edits.
- Retention or archiving will need a deliberate, privileged procedure (for example partition detach),
  not DELETE.
- The trigger must be diffed against the pilot's migration when the pilot is available.
