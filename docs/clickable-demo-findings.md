# Clickable demo: findings

Source: `reference/pilot/clickable-demo/delphin-agency-demo.html` (single file, roughly 900 lines, read in full).

> **Authority: lowest (6 of 6).** The pilot README calls the demo a "simplified illustration only. Never
> authoritative". Use it to know **what to look for** in the pilot. Every item still has to be confirmed
> against `nextjs-app/docs`, its tests and its source before it is ported. The demo is hand-written CSS
> rather than Tailwind, so **none of its CSS may go into `globals.css`.**

## 1. Application layout

| Area | What the demo shows |
|---|---|
| Shell | CSS grid with a **228 px left rail** and a fluid main area. Content `max-width: 1320px`, padding 22 px top, 16 px sides |
| Rail | Brand block: a square "D" mark (30 px, radius 7, accent background) next to **"Delphin Digital"** with "Agency console" below it. Grouped nav buttons follow; the active item has `aria-current="page"` and a soft accent background. Count badges sit on the right |
| Top bar | Sticky. Has a **"Menu"** button that only shows at ≤ 860 px; the rail becomes an off-canvas drawer (250 px). Everything else in the bar (demo flag, sync status, "Viewing as" persona switcher) is demo-only |
| Page header | Optional breadcrumb link above an `h1` (21 px), a muted sub-line, and actions on the right |
| Building blocks | Panel (header with title, description and actions; body), stat tile (label, large mono number, hint), table with uppercase muted headers, pill (neutral/ok/warn/bad/acc/info), progress bar with %, callout (info/warn/bad/ok), tabs (`role="tablist"`), step rail (tick states done/prog/blocked), kanban board (220 px columns, cards with a red left border when late), right-side **drawer** (≤ 560 px, `role="dialog"`, Escape closes), toast (bottom-right; errors stay 6 s, others 3 s), key/value `dl`, timeline, version cards with a feedback box |
| Type | IBM Plex Sans (UI) and IBM Plex Mono (codes and numbers, tabular figures), 14 px/1.5 |
| Palette | Teal-blue accent `#156a92`/`#0f5374`, background `#f4f7f8`, ok `#1e7f55`, warn `#9a6400`, bad `#b3372c`, info `#5b4bb5`. The demo also has a dark theme. **Do not reuse these values: the pilot's `globals.css` is authoritative** |
| Formatting | Dates `en-GB` (`16 Oct 2026`), money `en-US` USD, codes in mono |
| Window title | "Delphin Agency Console" |

### Navigation in the demo (compare with the scaffold's provisional `nav.ts`)

| Group | Items (label → page) |
|---|---|
| Overview | Dashboard |
| Clients | CRM & Clients · **Client Onboarding** |
| Delivery | Projects · **Tasks & Work** (badge: my open tasks) · Approvals (badge: awaiting my decision) |
| Services | **Services & Retainers** |
| Organisation | **Finance & Billing** (hidden without finance / view-money) · **Team & Roles** · **Activity log** |

The demo leaves out meetings, SEO, content, documents, reports, search, notifications and settings, all
of which the brief lists as pilot routes. It also has an **Activity log** page that the brief doesn't list.
→ The pilot's `nav.ts` decides the final list.

## 2. Roles and access

- Role keys: `SUPER_ADMIN`, `ACCOUNT_MANAGER`, `PROJECT_MANAGER`, `TEAM_LEAD`, `EMPLOYEE`, `FINANCE`.
  **There is no "Admin / Operations Manager"** in the demo, although the brief lists one. Check the pilot.
- The demo's permission strings (`clients.create`, `onboarding`, `access.verify`, `kpi.confirm`,
  `projects.create`, `tasks.create`, `client.decision`, `retainers`, `view.money`, `review`, `jobs.run`,
  `finance`) are simplified. **They are not the catalogue.**
- Capability matrix (Team & Roles page). Super Admin can do everything; otherwise:

  | Capability | Roles |
  |---|---|
  | Create clients & run onboarding | Account Manager |
  | Verify platform access | Account Manager, Project Manager, Team Lead |
  | Create projects | Account Manager, Project Manager |
  | Review deliverables | Project Manager, Team Lead |
  | Record client decisions | Account Manager |
  | See billing figures | Account Manager, Finance |
  | Create invoices & payments | Finance |

- **Record scope:** an Employee only sees clients they're on the team for or have a task on, and projects
  they have a task in. A record you can't see returns **"not found"**, never "forbidden".
- Onboarding is managed by the client's own Account Manager (or Super Admin). Other roles get a read-only view.

## 3. Features and business rules by module

### clients
- Create form fields: legal/business name (required), website, industry, Account Manager, primary contact,
  contact e-mail.
- **Duplicates:** the same normalised domain is a **hard block**. A similar normalised name is a
  **warning**, overridden with "This is a different business". Name normalisation: lower-case, `&` → "and",
  strip punctuation, drop `the inc llc ltd limited co corp company pvt private`.
- Code `CL-0001`. Creating a client auto-creates the onboarding checklist and an access checklist (GSC,
  GA4, Website CMS, Ahrefs, Google Drive).
- List columns: Client (+ code · domain), Status (Active / Onboarding / Contract pending), Onboarding
  progress, Account Manager, Projects.
- Client page tabs in the demo: Overview, Onboarding, Projects, Activity. The pilot has 13 tabs.
  Overview shows a "Next required action" callout.

### onboarding (13 steps)
1 Contract signed · 2 Client created · 3 Client profile completed (website, industry, contact + e-mail) ·
4 Questionnaire sent · 5 Questionnaire submitted · 6 Platform access collected · 7 Access verified ·
8 KPI targets defined & confirmed · 9 Client kickoff · 10 Internal team kickoff (needs a team) ·
11 Onboarding review · 12 Onboarding completed · 13 Project created / linked.

- Step states: todo / in progress / done / **blocked**. Rejected access blocks the whole onboarding.
- Access status flow: pending → requested → received → verified | rejected (or `not_required`).
  **Verify only from received**, only by verifier roles, and it records who verified it ("manual" check,
  passwords never stored).
- KPI = metric, baseline, target, unit. Each needs a **client confirmation** (recorded by the AM).
- Questionnaire: a single-use link valid **30 days**. Answers: business goals, products & services, target
  markets, target audiences, competitors, brand voice.
- **Review passes only when steps 1–10 are done. Completion re-checks: all access verified, all KPIs
  confirmed.** Completing makes the client Active and unlocks project creation.
- Progress % = completed steps ÷ 13.

### projects
- **Locked until onboarding completes** (enforced on the client page and on create).
- Code `PRJ-0001`. Created from the template **"SEO onboarding & foundation"** with 5 tasks
  (title, start offset days, duration, review, client approval): Baseline SEO audit (0, 5, ✓, —),
  Keyword research (0, 7, ✓, —), Technical fixes roadmap (5, 5, ✓, ✓), On-page optimisation of priority
  pages (12, 14, ✓, —), Month 1 performance report (25, 5, ✓, ✓).
- Progress = completed ÷ non-cancelled tasks. Project page: 4 stat tiles plus a kanban board with columns
  Backlog, Ready, In progress, Blocked, Internal review, Client approval, Completed.

### tasks
- Statuses: backlog, ready, in_progress, blocked, internal_review, client_approval, completed, cancelled.
- Number `T-n`. Overdue = due date before today and not completed/cancelled.
- Lists: My tasks · Awaiting my review · All I can see.
- **Tasks that need review or client approval can't be marked completed**; you "Submit for review"
  instead, with notes and a link. Each submission creates a **version** (v1, v2…).
- Only the assignee or a manager (PM / Team Lead) can work a task. Only managers reassign.
- The demo opens tasks in a drawer; the pilot has a `/tasks/:id` page (screenshot 10).

### approvals
- Stages: **internal** (the task's reviewer) and **client** (the client's AM records the decision).
- **No self-approval.** A submitter can't approve their own version, and a reviewer can't submit their
  own task for review.
- "Request changes" needs feedback. **Client decisions need a decision-maker and a channel**
  (Email / Call / Meeting / WhatsApp).
- Internal approval moves to the client stage if the task requires it; otherwise the task completes.
  Changes requested send the task back to in progress.

### services (retainers)
- One SEO retainer per client, only for clients whose onboarding is complete; it has a monthly amount.
- Recurring monthly templates: Monthly SEO audit (day 11, review), Keyword tracking update (day 4),
  Monthly client performance report (day 6, review). **Due dates move off weekends** (Saturday +2, Sunday +1).
- **Idempotent scheduler:** key `service | template | YYYY-MM`. Running it twice creates nothing new.
- The scheduler is run by roles with `jobs.run` (PM). Real cron is `POST /jobs/run`.

### finance
- Invoice `INV-YYYY-0001`, statuses Draft → Issued → Partially paid → Paid. Due date is today + 14.
- Total = amount × (1 + tax %), rounded to 2 dp (half-up for positive amounts). Default tax 10%.
- **A payment can't exceed the outstanding balance.**
- Tiles: Invoiced, Collected, Outstanding, Contracted / month ("contracted value, not revenue").
- Finance manages invoices; the Account Manager sees figures only. Money is hidden entirely from other
  roles (dashboard tiles and the retainer amount column too).

### dashboard
- Greeting "Good day, {first name}". Tiles: Active clients, In onboarding, Open tasks, Overdue tasks (red),
  Awaiting approval (internal · client). Roles that can see money also get Contracted / month and
  Outstanding receivables.
- Panels: My open work · Onboarding pipeline · Team workload (open / overdue per person) · Recent activity.

### team / activity
- People table (name, title, role pill, open tasks) and the capability matrix above. The demo says people
  are invited by e-mail and activate their own accounts.
- Activity log: newest first, "text — actor · time"; also scoped per client.

## 4. Applied to the scaffold (interim; every item is still marked provisional)

All of these are replaced when the pilot source arrives: `globals.css` byte for byte, `nav.ts` and
`permissions.ts` 1:1, primitives and shell verbatim.

| Scaffold item | What changed | Where |
|---|---|---|
| Design tokens | Demo palette (light + dark via `prefers-color-scheme` / `data-theme`), IBM Plex Sans/Mono (self-hosted via `@fontsource`, so no CSP change), 14 px/1.5 body, `shell` breakpoint at 861 px | `frontend/src/styles/globals.css`, `src/main.tsx` |
| Shell | 228 px rail with "D" mark and "Delphin Digital / Agency console", uppercase groups, badge slots, off-canvas drawer below 861 px, sticky top bar with "Menu"; dev builds show a "Viewing as" role switcher (the demo's persona selector) | `src/components/shell/*` |
| Navigation | Demo groups, labels and order; Finance & Billing only for roles that can see money; no icons (the demo has none) | `src/components/shell/nav.ts` |
| Primitives | Restyled to the demo (button, pill, panel, stat card, callout, toast, empty state, table, form fields) and added Panel, StatCard, Progress, Tabs, StepList, KeyValue, Timeline, Drawer | `src/components/ui/*`, gallery at `/__dev/ui` |
| Roles & permissions | Demo capability matrix as interim `domain.action` permissions on both sides; `admin` (brief only) has none. The backend enforces the catalogue only once `CATALOGUE_SOURCE = "pilot"` | `backend/app/authz/permissions.py`, `frontend/src/lib/permissions.ts` |
| Page titles | Demo h1s, marked `titleSource: 'demo'`: CRM & Clients, New client, Client onboarding, Projects, Tasks & work, Approvals, Services & retainers, Finance & billing, Team & roles | `frontend/src/features/*/route-specs.ts` |
| Activity log | New module slot on both sides, route `/activity` | `backend/app/modules/activity`, `frontend/src/features/activity` |
| Formatting | Dates en-GB (UTC), money en-US USD, code padding | `frontend/src/lib/format.ts` |
| Window title | "Delphin Agency Console" | `index.html`, `DocumentTitle.tsx` |
| Money rounding | Half-up noted as the demo's behaviour | `backend/app/db/types.py` |

### Not applied (conflicts or out of scaffold scope)

| Item | Why |
|---|---|
| `/team` title "Team & roles" vs pilot README screenshot "Team & Employees" | Used the demo h1; the README describes the screen, not necessarily its heading. Check `16-team.png` |
| Admin / Operations Manager role | Kept: the brief lists it, the demo doesn't. Confirm in `permissions.ts` |
| Routes the demo rail omits (meetings, SEO, content, documents, reports, search, notifications, settings) | Still registered and reachable by URL; the pilot's `nav.ts` decides placement |
| Demo-only chrome (shared-data banner, sync status, "Reset demo data") | Not part of the product |
| Business behaviour (section 3) | Feature work, ported module by module (auth → clients → onboarding first) |
