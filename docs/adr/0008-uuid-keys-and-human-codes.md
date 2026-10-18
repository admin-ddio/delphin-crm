# 0008. UUID primary keys plus human codes from a counter table

- Status: accepted
- Date: 2026-10-16

## Context and problem statement

Records need non-guessable, merge-safe identifiers, but users work with short codes such as `CL-0001`,
`PRJ-0001` and `INV-YYYY-0001`. The pilot uses a `Counter` table for these codes.

## Decision outcome

- Primary keys are UUIDs (`gen_random_uuid()` server default plus a Python default).
- Human codes come from `counters` through `platform.system.counters.next_value()`. It is a single
  `INSERT … ON CONFLICT DO UPDATE … RETURNING`, so it is transactional, concurrency-safe, and a
  rolled-back transaction does not consume a number.
- Formatting is `format_code(prefix, n)`; per-year keys (for example `invoice:2026`) give yearly
  sequences.

### Consequences

- Each module stores its code in a unique column next to the UUID.
- The counter row is a hot spot under heavy concurrent creation of one entity type; acceptable for an
  agency CRM.
