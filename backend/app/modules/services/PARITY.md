# Services: parity checklist

> **Status: built (2026-10-28) from the services plan and the clickable demo, pending pilot
> confirmation.** Every `TODO(pilot-port)` below must be filled **from the pilot source**,
> never from memory. See [docs/pilot-parity.md](../../../../docs/pilot-parity.md).

| | |
|---|---|
| Pilot sources | `services/retainers.ts` (services and authz under `reference/pilot/nextjs-app/src/server/`, API routes under `src/app/api/`) |
| Pilot routes | /services, /services/:id, /services/retainers, /services/templates, /services/workspace/:csId |
| Backend slot | `backend/app/modules/services/` → `/api/v1/services` |
| Frontend slot | `frontend/src/features/services/` |

## What Delphin sells (user, 2026-10-27)

| Service | Kind | Delivering department | Template |
|---|---|---|---|
| SEO | monthly retainer | SEO Team | setup (5 foundation tasks) + 6 monthly tasks |
| Social Media Marketing | monthly retainer | Social Media Team | setup (4) + 5 monthly tasks |
| SEO-friendly Website | project | Web Development Team | 8 delivery phases |
| Web Application | project | Application Development Team | 8 delivery phases |
| Mobile Application | project | Application Development Team | 7 delivery phases |

## Actions → REST endpoints

| Action | Method | Path | Permission | Status |
|---|---|---|---|---|
| catalogue | GET | `/api/v1/services/types` | signed in | built |
| templates: read / replace | GET / PUT | `/api/v1/services/types/{key}/templates` | read: signed in; write: `services.templates.manage` | built |
| list (tiles, filters) | GET | `/api/v1/services` | scoped | built |
| add services to a client | POST | `/api/v1/services/clients/{client_id}` | `services.manage` + the client's AM | built |
| choose services at client creation | POST | `/api/v1/clients` (`services`) | `clients.create` | built |
| workspace | GET | `/api/v1/services/{id}` | scoped | built |
| start options / start | GET / POST | `…/{id}/start-options`, `…/{id}/start` | `services.manage` + AM | built |
| pause / resume / complete / cancel | POST | `…/{id}/{action}` | `services.manage` + AM | built |
| generate this month | POST | `…/{id}/generate` | `jobs.run`, `services.manage` or the service's PM | built |
| monthly job | job | `services.generate_monthly` | cron / `scripts/run_jobs.py` | built |

## Business rules

- [x] Services are chosen at client creation (at least one); more can be added later
- [x] One open (planned / active / paused) SEO and one Social Media retainer per client (partial unique index); projects may repeat
- [x] The onboarding access checklist is the union of the services' items (+ Google Drive); a service added while onboarding is open extends it
- [x] A service starts only after onboarding is completed; starting creates its delivery project (`ProjectService.create_for_service`) and completes onboarding step 13 ("Delivery started")
- [x] Default Project Manager = the delivering department's delivery manager (org structure)
- [x] Template tasks go to the client team member covering the task's area; the PM reviews
- [x] Monthly tasks start the month after the retainer starts (setup covers month 1)
- [x] Recurring task generation is idempotent per period (unique `(client_service_id, template_task_id, occurrence_key)`); due dates move off weekends (Sat +2, Sun +1)
- [x] Only active retainers generate; paused / completed / cancelled don't
- [x] Fees are visible to `finance.view` (Account Managers, Finance); hidden from others
- [x] Template edits retire removed tasks (history stays linked)
- [x] Every change audited (`service.*`, `service_template.updated`) and on the client timeline
- [ ] TODO(pilot-port): invoicing from retainer fees (Finance module)

## Record-level scope

- `services.view_all` (AM, PM, Finance, Super Admin) sees every service; others see services of clients they can see (ClientScope) or that they manage. Hidden records → 404.

## Entities (interim, migration `0011_services`)

- `service_types`, `service_template_tasks`, `client_services`, `service_occurrences`
- TODO(pilot-port): reconcile with schema.prisma
