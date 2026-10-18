# Testing

| Layer | Tool | Location | Run |
|---|---|---|---|
| Backend unit | pytest | `backend/tests/unit` | `make test-backend` |
| Backend contract (OpenAPI, slots) | pytest | `backend/tests/contract` | `make test-backend` |
| Backend integration (Postgres) | pytest | `backend/tests/integration` | `make test-backend` |
| Frontend unit/component | Vitest + Testing Library | `frontend/tests/unit` | `make test-frontend` |
| E2E smoke | Playwright | `frontend/tests/e2e/smoke.spec.ts` | `make e2e` |
| Visual parity | Playwright + pixelmatch | `frontend/tests/e2e/visual.spec.ts` | `make e2e` |

## Backend database tests

Integration tests use `TEST_DATABASE_URL` (the `<db>_test` database on the Compose Postgres). Once per
session the fixture creates the database if missing and **round-trips the migrations** (upgrade head →
downgrade base → upgrade head). Each test then runs in a transaction that is rolled back.

Coverage: at least 90% on `app/core`, `app/authz` and `app/platform` (`fail_under` in `pyproject.toml`).

## Visual parity

- Viewport 1440 × 900, `deviceScaleFactor: 1`, light scheme, reduced motion, fonts loaded, animations
  and caret disabled.
- Baselines are read **read-only** from `reference/pilot/screenshots/`; the comparison crops the same
  region from both images and fails above a 1% differing-pixel ratio. Actual, expected and diff images
  are attached to the Playwright report.
- While a baseline is missing the test **skips with a reason**; with `REQUIRE_PILOT=true` it fails.
  Baselines are never faked.
- Business screens 01–17 are `test.fixme` entries; each feature port turns its entries on.

### Capturing a new baseline (for example the `/__dev/ui` gallery)

Run the pilot (see `reference/pilot/README.md`), capture at 1440 × 900, light theme, full page, and save
it as `reference/pilot/screenshots/NN-name.png`. That is the only write to `reference/` ever allowed.

## Token drift

`frontend/tests/unit/token-drift.test.ts` fails if `src/styles/globals.css` differs by even one byte
from the pilot's `globals.css`.
