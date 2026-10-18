# UI primitives: porting checklist

Every file in this folder is **provisional** (currently styled after the clickable demo, see
`docs/clickable-demo-findings.md`) until it is replaced by a verbatim port of
`reference/pilot/nextjs-app/src/components/ui/*.tsx`. Port the JSX structure and **class strings
unchanged**; swap only framework specifics (`next/link` → `@/components/ui/Link`, server data → props).

| Primitive | Status | Notes |
|---|---|---|
| Button, LinkButton | provisional | |
| Badge, StatusBadge | provisional (Badge only) | StatusBadge needs the pilot's status → tone map |
| PageHeader | provisional | |
| Card, Panel, StatCard | provisional (demo look) | |
| EmptyState | provisional | |
| Alert | provisional | |
| Toast | provisional visuals | provider/hook API is scaffold infra; keep it |
| Dialog | provisional visuals | keep native `<dialog>` ARIA wiring |
| Link | provisional | no-prefetch behaviour preserved |
| Progress | provisional (demo look) | `Data.tsx` |
| Tabs | provisional (demo look) | `Data.tsx`; add `tabpanel` wiring when porting |
| Avatar | not started | |
| KeyValue | provisional (demo look) | `Data.tsx` |
| DataTable, Pagination | not started | uses `.table` from globals.css |
| SectionTitle | not started | |
| Timeline | provisional (demo look) | `Data.tsx` |
| FilterBar, FilterSelect, FilterSearch | not started | |
| Form fields | not started | `.input` / `.label`, labelled inputs |
| DateTime | not started | pilot's date formatting and locale |
| StepList, Drawer | provisional (demo look) | onboarding step rail; task drawer |

When a primitive is ported, add it to the `/__dev/ui` gallery and capture its pilot baseline.
