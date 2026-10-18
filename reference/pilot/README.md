# Pilot reference: the source of truth

This folder holds the **pilot**, the first working version of the Delphin Digital Agency CRM & Operations Platform. The new build (React + FastAPI + PostgreSQL + Docker Compose at the repository root) must **reproduce its behaviour and its UI pixel for pixel**.

> **Read-only.** Nothing in `reference/` is built, deployed, imported or edited by the new stack. Agents read from it. Agents never write to it.

## What is here

| Path | What it is | Use it for |
|---|---|---|
| `nextjs-app/` | The complete pilot app (Next.js 15, Server Actions, Prisma 6, PostgreSQL 16). It ships with 41 Vitest tests and 7 Playwright journeys. | Behaviour, rules, data model and exact UI markup |
| `nextjs-app/docs/` | Architecture, schema, permissions, onboarding workflow, modules, integrations, testing, deployment, known limitations | Written requirements: **read these first** |
| `nextjs-app/prisma/schema.prisma` | The data model: 63 models and 40 enums, with constraints and indexes | Port to SQLAlchemy 2.0 + Alembic |
| `nextjs-app/prisma/migrations/` | SQL migrations, including the append-only `AuditLog` trigger and partial unique indexes | DB-level guarantees that must survive the port |
| `nextjs-app/src/server/services/` | Business logic, one file per domain | Port to FastAPI service layer |
| `nextjs-app/src/server/authz/` | Permission catalogue, actor, record-level scopes | Port to FastAPI dependencies and query scopes |
| `nextjs-app/src/app/actions/` | Server Actions (the pilot's write API) | Becomes REST endpoints under `/api/v1` |
| `nextjs-app/src/app/**/page.tsx` | Every screen (about 70 routes) | Becomes React Router routes |
| `nextjs-app/src/app/globals.css` | Design tokens and component classes (Tailwind 4 `@theme`) | **Copy verbatim** into the frontend |
| `nextjs-app/src/components/` | UI primitives, shell (sidebar and top bar), forms, kanban, calendar, tables | Port JSX and class strings unchanged |
| `nextjs-app/tests/` | Unit, integration and E2E tests | Parity test cases for the new stack |
| `screenshots/` | 18 full-page captures of the pilot at a **1440 × 900 viewport** | Baselines for visual parity checks |
| `clickable-demo/index.html` | Single-file, browser-only demo of the main flows, also published on claude.ai | Quick look at flows and wording without running anything |

### Screenshot index

| File | Screen |
|---|---|
| `00-login.png` | Sign in |
| `01-dashboard.png` | Organisation dashboard |
| `02-clients.png` | CRM & Clients list |
| `03-client-overview.png` | Client overview |
| `04-onboarding-summary.png` … `07-onboarding-review.png` | Onboarding: summary, access, KPIs, review |
| `08-project.png`, `09-project-board.png` | Project overview and kanban board |
| `10-task.png` | Task detail with versions and review |
| `11-approval.png` | Approval decision |
| `12-retainer-workspace.png` | Service / retainer workspace |
| `13-content.png` | Content & Social |
| `14-invoice.png`, `15-finance.png` | Invoice detail and finance overview |
| `16-team.png` | Team & Employees |
| `17-settings-roles.png` | Settings → Roles & permissions |

## Order of authority (when sources disagree)

1. `nextjs-app/docs/*.md`: stated requirements and business rules
2. `nextjs-app/tests/**`: proven behaviour
3. `nextjs-app/src/server/**` and `prisma/`: implemented behaviour
4. `nextjs-app/src/components/**`, `globals.css`: exact visual implementation
5. `screenshots/`: visual ground truth for layout, spacing and colour
6. `clickable-demo/`: simplified illustration only. Never authoritative.

## Running the pilot (optional, for new screenshots)

You only need this when a screen has no screenshot and you need a pixel baseline.

```bash
cd reference/pilot/nextjs-app
npm ci
cp .env.example .env            # set DATABASE_URL to a local Postgres 16
npx prisma migrate deploy && npm run db:seed
SEED_DEMO_DATA=true SEED_DEMO_PASSWORD='<dev-only password>' npm run db:seed
npm run build && npm start      # http://localhost:3000, capture at 1440×900
```

Save new captures to `screenshots/` as `NN-screen-name.png`. Use a 1440 × 900 viewport, light theme and full page. This is the only write to `reference/` that is ever allowed.

## Rules

- Never copy `.env`, `node_modules/`, `.next/`, `storage*/`, `test-results/` or `playwright-report/` out of this folder.
- Never import pilot code at runtime. Port it.
- The pilot holds **no business data**. Do not invent clients, revenue or metrics for the new build either.
