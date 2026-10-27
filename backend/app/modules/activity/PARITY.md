# Activity: parity checklist

> **Status: built (2026-10-28) from the clickable demo.** Confirm the pilot has `/activity`
> before treating it as final. See [docs/clickable-demo-findings.md](../../../../docs/clickable-demo-findings.md).

| | |
|---|---|
| Pilot sources | TODO(pilot-port): unknown (demo: "Activity log" page) |
| Pilot routes | `/activity` (demo) |
| Backend slot | `backend/app/modules/activity/` → `/api/v1/activity` |
| Frontend slot | `frontend/src/features/activity/` |

## Actions → REST endpoints

| Action | Method | Path | Permission | Status |
|---|---|---|---|---|
| list (filters, cursor) | GET | `/api/v1/activity?client_id&person_id&area&since&until&before&limit` | signed in, scoped | built |

## Business rules (from the demo)

- [x] Newest first; each entry shows the text, the actor ("System" when none) and the time
- [x] Scoped to clients the viewer can see (ClientScope); also shown per client (client Activity tab)
- [x] Areas from the event verb: clients, onboarding, projects & tasks, approvals, documents, meetings, services, other
- [x] Keyset pagination (`before` = "occurred_at|id")
- [x] Organisation / HR changes stay in their own audit logs (Organization & Roles → Audit log)

## Entities

- None: reads `activity_events` from migration 0001 (written by `platform.activity.ActivityRecorder`).
