# Pilot parity matrix

The master checklist mapping every pilot route, Server Action, API route and business rule to its slot
in the rebuild. Per-module detail lives in `backend/app/modules/<slot>/PARITY.md` and
`frontend/src/features/<slot>/PARITY.md`.

> **The pilot was not present when this matrix was created.** `reference/pilot/` was an empty
> placeholder. The rows below come **only** from the scaffold brief
> (`.claude/agents/scaffold-architect.md` §7 and §9) and the pilot README's screenshot index. Every
> `TODO(pilot-port)` must be completed by reading the pilot, never from memory. In particular:
>
> - pilot page paths are written `src/app/…/<route>/page.tsx` because the real folder structure
>   (route groups and the like) is unknown;
> - all page titles are provisional;
> - the Server Actions, API routes and data-model sections are empty until they are read from the pilot.

Status values: `not-started` → `in-progress` → `ported` → `verified` (tests and visual parity pass).

**Clickable demo:** what `reference/pilot/clickable-demo/delphin-agency-demo.html` shows (layout, nav,
roles, the detail behind each rule) is recorded in [clickable-demo-findings.md](clickable-demo-findings.md).
It is the lowest authority: use it as a pointer, and confirm every item in the pilot source.

## Known gaps (scaffold)

| Gap | Impact | Resolution |
|---|---|---|
| Pilot source absent | Tokens, primitives, shell, nav, permission catalogue and titles are provisional | Add the pilot to `reference/pilot/`; follow README "When the pilot arrives" |
| `globals.css` not ported | Token-drift test skipped | Copy the file byte for byte |
| No screenshots | Visual tests skip | Add `reference/pilot/screenshots/*.png` |
| No `/__dev/ui` pilot baseline | Gallery visual test skips | Capture a primitives gallery from a running pilot (docs/testing.md) |
| Screenshot names `05-onboarding-access.png` and `06-onboarding-kpis.png` | Inferred from the README's "04 … 07" range | Confirm against the real files |
| Platform-core table shapes | Follow the brief, not `schema.prisma` | Reconcile in a new migration |
| Lock files absent | `uv.lock` and `pnpm-lock.yaml` not generated (no toolchain where scaffolded) | `make lock` |

## Routes

| Pilot source | Target slot → route (layout) | Provisional title | Baseline | Status |
|---|---|---|---|---|
| `src/app/…/approvals/page.tsx` | `features/approvals` → `/approvals` (app) | Approvals |  | not-started |
| `src/app/…/approvals/new/page.tsx` | `features/approvals` → `/approvals/new` (app) | New approval |  | not-started |
| `src/app/…/approvals/:id/page.tsx` | `features/approvals` → `/approvals/:id` (app) | Approval | 11-approval.png | not-started |
| `src/app/…/login/page.tsx` | `features/auth` → `/login` (public) | Sign in | 00-login.png | not-started |
| `src/app/…/forgot-password/page.tsx` | `features/auth` → `/forgot-password` (public) | Forgot password |  | not-started |
| `src/app/…/reset-password/:token/page.tsx` | `features/auth` → `/reset-password/:token` (public) | Reset password |  | not-started |
| `src/app/…/activate/:token/page.tsx` | `features/auth` → `/activate/:token` (public) | Activate account |  | not-started |
| `src/app/…/account/page.tsx` | `features/auth` → `/account` (app) | My account |  | not-started |
| `src/app/…/clients/page.tsx` | `features/clients` → `/clients` (app) | CRM & Clients | 02-clients.png | not-started |
| `src/app/…/clients/new/page.tsx` | `features/clients` → `/clients/new` (app) | New client |  | not-started |
| `src/app/…/clients/:id/page.tsx` | `features/clients` → `/clients/:id` (app) | Client overview | 03-client-overview.png | not-started |
| `src/app/…/clients/:id/edit/page.tsx` | `features/clients` → `/clients/:id/edit` (app) | Edit client |  | not-started |
| `src/app/…/clients/:id/contacts/page.tsx` | `features/clients` → `/clients/:id/contacts` (app) | Contacts |  | not-started |
| `src/app/…/clients/:id/onboarding/page.tsx` | `features/clients` → `/clients/:id/onboarding` (app) | Onboarding | 04-onboarding-summary.png, 05-onboarding-access.png, 06-onboarding-kpis.png, 07-onboarding-review.png | not-started |
| `src/app/…/clients/:id/projects/page.tsx` | `features/clients` → `/clients/:id/projects` (app) | Projects |  | not-started |
| `src/app/…/clients/:id/tasks/page.tsx` | `features/clients` → `/clients/:id/tasks` (app) | Tasks |  | not-started |
| `src/app/…/clients/:id/services/page.tsx` | `features/clients` → `/clients/:id/services` (app) | Services |  | not-started |
| `src/app/…/clients/:id/kpis/page.tsx` | `features/clients` → `/clients/:id/kpis` (app) | KPIs |  | not-started |
| `src/app/…/clients/:id/meetings/page.tsx` | `features/clients` → `/clients/:id/meetings` (app) | Meetings |  | not-started |
| `src/app/…/clients/:id/communications/page.tsx` | `features/clients` → `/clients/:id/communications` (app) | Communications |  | not-started |
| `src/app/…/clients/:id/documents/page.tsx` | `features/clients` → `/clients/:id/documents` (app) | Documents |  | not-started |
| `src/app/…/clients/:id/approvals/page.tsx` | `features/clients` → `/clients/:id/approvals` (app) | Approvals |  | not-started |
| `src/app/…/clients/:id/billing/page.tsx` | `features/clients` → `/clients/:id/billing` (app) | Billing |  | not-started |
| `src/app/…/clients/:id/activity/page.tsx` | `features/clients` → `/clients/:id/activity` (app) | Activity |  | not-started |
| `src/app/…/content/page.tsx` | `features/content` → `/content` (app) | Content & Social | 13-content.png | not-started |
| `src/app/…/content/new/page.tsx` | `features/content` → `/content/new` (app) | New content |  | not-started |
| `src/app/…/content/:id/page.tsx` | `features/content` → `/content/:id` (app) | Content |  | not-started |
| `src/app/…/dashboard/page.tsx` | `features/dashboard` → `/dashboard` (app) | Dashboard | 01-dashboard.png | not-started |
| `src/app/…/documents/page.tsx` | `features/documents` → `/documents` (app) | Documents |  | not-started |
| `src/app/…/finance/page.tsx` | `features/finance` → `/finance` (app) | Finance | 15-finance.png | not-started |
| `src/app/…/finance/invoices/page.tsx` | `features/finance` → `/finance/invoices` (app) | Invoices |  | not-started |
| `src/app/…/finance/invoices/new/page.tsx` | `features/finance` → `/finance/invoices/new` (app) | New invoice |  | not-started |
| `src/app/…/finance/invoices/:id/page.tsx` | `features/finance` → `/finance/invoices/:id` (app) | Invoice | 14-invoice.png | not-started |
| `src/app/…/finance/expenses/page.tsx` | `features/finance` → `/finance/expenses` (app) | Expenses |  | not-started |
| `src/app/…/meetings/page.tsx` | `features/meetings` → `/meetings` (app) | Meetings |  | not-started |
| `src/app/…/meetings/new/page.tsx` | `features/meetings` → `/meetings/new` (app) | New meeting |  | not-started |
| `src/app/…/meetings/:id/page.tsx` | `features/meetings` → `/meetings/:id` (app) | Meeting |  | not-started |
| `src/app/…/notifications/page.tsx` | `features/notifications` → `/notifications` (app) | Notifications |  | not-started |
| `src/app/…/onboarding/page.tsx` | `features/onboarding` → `/onboarding` (app) | Onboarding |  | not-started |
| `src/app/…/q/:token/page.tsx` | `features/onboarding` → `/q/:token` (bare) | Client questionnaire |  | not-started |
| `src/app/…/projects/page.tsx` | `features/projects` → `/projects` (app) | Projects |  | not-started |
| `src/app/…/projects/new/page.tsx` | `features/projects` → `/projects/new` (app) | New project |  | not-started |
| `src/app/…/projects/:id/page.tsx` | `features/projects` → `/projects/:id` (app) | Project | 08-project.png, 09-project-board.png | not-started |
| `src/app/…/reports/page.tsx` | `features/reports` → `/reports` (app) | Reports |  | not-started |
| `src/app/…/search/page.tsx` | `features/search` → `/search` (app) | Search |  | not-started |
| `src/app/…/seo/page.tsx` | `features/seo` → `/seo` (app) | SEO |  | not-started |
| `src/app/…/seo/:clientId/page.tsx` | `features/seo` → `/seo/:clientId` (app) | SEO |  | not-started |
| `src/app/…/services/page.tsx` | `features/services` → `/services` (app) | Services |  | not-started |
| `src/app/…/services/:id/page.tsx` | `features/services` → `/services/:id` (app) | Service |  | not-started |
| `src/app/…/services/retainers/page.tsx` | `features/services` → `/services/retainers` (app) | Retainers |  | not-started |
| `src/app/…/services/templates/page.tsx` | `features/services` → `/services/templates` (app) | Service templates |  | not-started |
| `src/app/…/services/workspace/:csId/page.tsx` | `features/services` → `/services/workspace/:csId` (app) | Service workspace | 12-retainer-workspace.png | not-started |
| `src/app/…/settings/page.tsx` | `features/settings` → `/settings` (app) | Settings |  | not-started |
| `src/app/…/settings/roles/page.tsx` | `features/settings` → `/settings/roles` (app) | Roles & permissions | 17-settings-roles.png | not-started |
| `src/app/…/settings/onboarding/page.tsx` | `features/settings` → `/settings/onboarding` (app) | Onboarding settings |  | not-started |
| `src/app/…/settings/automation/page.tsx` | `features/settings` → `/settings/automation` (app) | Automation |  | not-started |
| `src/app/…/settings/jobs/page.tsx` | `features/settings` → `/settings/jobs` (app) | Jobs |  | not-started |
| `src/app/…/settings/integrations/page.tsx` | `features/settings` → `/settings/integrations` (app) | Integrations |  | not-started |
| `src/app/…/settings/audit/page.tsx` | `features/settings` → `/settings/audit` (app) | Audit log |  | not-started |
| `src/app/…/tasks/page.tsx` | `features/tasks` → `/tasks` (app) | Tasks |  | not-started |
| `src/app/…/tasks/new/page.tsx` | `features/tasks` → `/tasks/new` (app) | New task |  | not-started |
| `src/app/…/tasks/:id/page.tsx` | `features/tasks` → `/tasks/:id` (app) | Task | 10-task.png | not-started |
| `src/app/…/team/page.tsx` | `features/team` → `/team` (app) | Team & Employees | 16-team.png | not-started |
| `src/app/…/team/employees/page.tsx` | `features/team` → `/team/employees` (app) | Employees |  | not-started |
| `src/app/…/team/employees/new/page.tsx` | `features/team` → `/team/employees/new` (app) | New employee |  | not-started |
| `src/app/…/team/employees/:id/page.tsx` | `features/team` → `/team/employees/:id` (app) | Employee |  | not-started |
| `src/app/…/team/teams/page.tsx` | `features/team` → `/team/teams` (app) | Teams |  | not-started |
| `src/app/…/team/teams/:id/page.tsx` | `features/team` → `/team/teams/:id` (app) | Team |  | not-started |
| `src/app/…/team/workload/page.tsx` | `features/team` → `/team/workload` (app) | Workload |  | not-started |

## Server Actions → REST endpoints

| Pilot source | Target slot (endpoint) | Rule or behaviour | Pilot test | Status |
|---|---|---|---|---|
| TODO(pilot-port): one row per export in `reference/pilot/nextjs-app/src/app/actions/*` | | | | not-started |

## Pilot API routes

| Pilot source | Target slot (endpoint) | Rule or behaviour | Pilot test | Status |
|---|---|---|---|---|
| `src/app/api/files/…` | `documents` → `GET /api/v1/files/{file_id}` (stub: 401/501) | Re-checks access on every request; restricted documents | TODO | not-started |
| `src/app/api/export/…` | `reports` → `GET /api/v1/reports/export.csv` (stub: 401/501) | CSV export | TODO | not-started |
| `src/app/api/cron/run/…` | `jobs` → `POST /api/v1/jobs/run` (bearer check live, run is a 501 stub) | Bearer `CRON_SECRET` | TODO | not-started |
| TODO(pilot-port): any other `src/app/api/**` route | | | | not-started |

## Business rules

| Pilot source | Target slot | Rule or behaviour | Pilot test | Status |
|---|---|---|---|---|
| services/clients.ts | `clients` service | Duplicate client detection by normalised domain and name | TODO | not-started |
| services/onboarding.ts, docs/onboarding-workflow.md | `onboarding` service | 13 onboarding steps with server-side gating | TODO | not-started |
| services/onboarding.ts | `onboarding` service | Review requires steps 1–10 | TODO | not-started |
| services/onboarding.ts | `onboarding` service | Completion requires all access verified and KPIs client-confirmed | TODO | not-started |
| services/projects.ts | `projects` service | Project creation locked until onboarding completes | TODO | not-started |
| services/tasks.ts | `tasks` service | Tasks requiring review cannot be completed directly | TODO | not-started |
| services/approvals.ts | `approvals` service | No self-approval | TODO | not-started |
| services/approvals.ts | `approvals` service | Client-stage decisions need a decision-maker and a channel | TODO | not-started |
| services/retainers.ts, jobs.ts | `services` + `jobs` | Recurring task generation idempotent per period (partial unique index on `(client_service_id, recurring_template_id, occurrence_key)`) | TODO | not-started |
| services/finance.ts | `finance` service | Payments cannot exceed the balance | TODO | not-started |
| services/finance.ts, authz | `finance` + every module that returns money | Financial fields stripped without permission | TODO | not-started |
| services/documents.ts | `documents` service | Restricted documents | TODO | not-started |
| services/admin.ts | `settings` service | Last Super Admin cannot be removed | TODO | not-started |
| prisma/migrations (AuditLog trigger) | migration `0001` + `platform/audit` | Append-only audit | `tests/integration/test_database.py` | **ported (scaffold)**: trigger to be diffed against the pilot's |
| src/server/authz (scope merge bug) | `authz/scopes.py` | Scopes compose with AND, never dict-merged | `tests/unit/test_scopes.py` | **ported (scaffold)** |
| server/auth | `core/security.py` + `auth` | Login rate limit counts failed attempts per account only | `tests/unit/test_security.py` (in-memory) | interface only |
| `forbidden()` | `core/errors.py` | Production redaction of forbidden errors | `tests/unit/test_errors.py` | **ported (scaffold)**: wording to be checked against the pilot |
| TODO(pilot-port): every other rule in `docs/*.md` | | | | not-started |

## Data model to port

From `reference/pilot/nextjs-app/prisma/schema.prisma` (63 models and 40 enums per the pilot README), grouped
by module, with constraints and indexes. **TODO(pilot-port): fill this in from the schema.**

| Module | Prisma model / enum | Target table / type | Constraints & indexes | Status |
|---|---|---|---|---|
| services | (recurrence model) | TODO | Partial unique `(client_service_id, recurring_template_id, occurrence_key)` | not-started |
| TODO | | | | |

## Pilot tests to port

The pilot README lists 41 Vitest tests and 7 Playwright journeys. **TODO(pilot-port): one row per test.**

| Pilot test | Target | Status |
|---|---|---|
| TODO | | not-started |
