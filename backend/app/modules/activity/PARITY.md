# Activity: parity checklist

> **Status: not started.** Known only from the clickable demo; the scaffold brief lists no
> `/activity` route. Confirm the pilot has it before porting. See
> [docs/clickable-demo-findings.md](../../../../docs/clickable-demo-findings.md).

| | |
|---|---|
| Pilot sources | TODO(pilot-port): unknown (demo: "Activity log" page) |
| Pilot routes | `/activity` (demo) |
| Backend slot | `backend/app/modules/activity/` → `/api/v1/activity` |
| Frontend slot | `frontend/src/features/activity/` |

## Actions → REST endpoints

| Pilot Server Action | Method | Path | Permission | Status |
|---|---|---|---|---|
| (list) | GET | `/api/v1/activity` | TODO | not-started |

## Business rules (from the demo, to confirm)

- [ ] Newest first; each entry shows the text, the actor and the time
- [ ] Also shown per client (client Activity tab), scoped to records the actor can see
- [ ] Every mutation in the app writes one entry (platform.activity.ActivityRecorder)

## Entities to port

- None: uses `activity_events` from migration 0001.
