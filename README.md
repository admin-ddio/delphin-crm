# Delphin Digital Agency CRM & Operations Platform

The production rebuild of the Delphin CRM: a **React + FastAPI + PostgreSQL** monorepo run with
**Docker Compose**. It must reproduce the pilot in [`reference/pilot/`](reference/pilot/README.md)
**feature for feature and pixel for pixel**.

> **Status: scaffold only.** Every pilot module has an empty slot, every pilot route renders a
> placeholder, and the platform foundation (config, errors, security, authz plumbing, audit, DB
> baseline, design-system slot, tests, CI) is in place. Business features are ported one module at
> a time; see [docs/pilot-parity.md](docs/pilot-parity.md).
>
> **The pilot has not been added yet.** `reference/pilot/` is an empty placeholder, so design tokens,
> UI primitives, the nav model and the permission catalogue are **provisional stand-ins** marked
> `PROVISIONAL` / `TODO(pilot-port)`. See [What to do when the pilot arrives](#when-the-pilot-arrives).

## Quick start

Prerequisites: Docker Desktop (Compose v2), GNU make and bash (Git Bash or WSL on Windows).

```bash
make lock         # first time only: generate backend/uv.lock and frontend/pnpm-lock.yaml
make up           # creates .env from .env.example, builds, starts, waits until healthy
open http://localhost:5173        # API docs: http://localhost:5173/api/docs
```

Edit `.env` and replace every `change-me` before sharing the stack with anyone.

## Make targets

| Target | What it does |
|---|---|
| `make up` / `down` / `logs` / `ps` | Dev stack lifecycle (hot reload for backend and frontend) |
| `make migrate` | `alembic upgrade head` |
| `make makemigration name=…` | Autogenerate a revision (review it by hand) |
| `make migrate-check` | Fail if models and migrations drift (`alembic check`) |
| `make seed-config` | Upsert default roles + permission catalogue (configuration only, no business data) |
| `make gen-api` | Regenerate `frontend/src/api/schema.d.ts` from the backend OpenAPI schema |
| `make lint` / `format` | ruff + import-linter + eslint + prettier |
| `make typecheck` | `mypy --strict` + `tsc` |
| `make test` | pytest (unit, contract, integration on a test DB) + vitest |
| `make e2e` | Playwright smoke + visual parity vs pilot screenshots |
| `make check` | Everything CI runs before e2e |
| `make prod-up` | Production profile: nginx edge on http://localhost:8080 |
| `make secrets-scan` | gitleaks |
| `make clean` | Remove containers, volumes and build output |
| `make lock` | Re-pin dependencies |

## Repository map

```
backend/            FastAPI app (app/core, db, authz, platform, modules/<slot>, api), Alembic, tests
frontend/           Vite + React 19 SPA (components/ui, components/shell, features/<slot>, lib), tests
infra/              Postgres init SQL; nginx notes
docs/               architecture, development, conventions, API, security, testing, deployment, ADRs
reference/pilot/    READ-ONLY pilot (source of truth). Never built, imported or edited
.claude/agents/     scaffold-architect agent definition
compose*.yaml       dev (base + override) and production (base + prod) stacks
Makefile            the only entry point
```

## When the pilot arrives

1. Copy it into `reference/pilot/` (`nextjs-app/`, `screenshots/`, `clickable-demo/`).
2. Copy `reference/pilot/nextjs-app/src/app/globals.css` over `frontend/src/styles/globals.css`
   byte for byte; `make test-frontend` (token-drift test) must pass.
3. Port `permissions.ts` into `backend/app/authz/permissions.py` and `frontend/src/lib/permissions.ts`.
4. Port `nav.ts`, the shell and the UI primitives verbatim (`frontend/src/components/ui/PORTING.md`).
5. Verify every route title against the pilot's `page.tsx` files.
6. Reconcile the platform-core tables with `schema.prisma` and its migrations.
7. Fill `docs/pilot-parity.md` and each module's `PARITY.md` from the pilot.
8. Set the CI variable `REQUIRE_PILOT=true` so missing baselines fail instead of skip.

## Documentation

[Architecture](docs/architecture.md) · [Development](docs/development.md) ·
[Conventions](docs/conventions.md) · [API guidelines](docs/api-guidelines.md) ·
[Security](docs/security.md) · [Testing](docs/testing.md) · [Deployment](docs/deployment.md) ·
[Pilot parity](docs/pilot-parity.md) · [ADRs](docs/adr/)
