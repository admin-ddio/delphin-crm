/**
 * /activity: the activity log (clickable demo): "text — actor · time", newest
 * first, for clients the viewer can see. Filters: client, person, area, dates.
 * Organisation and HR changes are in Organization & Roles → Audit log (linked).
 */
import { useMemo } from 'react';
import { useSearchParams } from 'react-router';

import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Panel } from '@/components/ui/Card';
import { EmptyState } from '@/components/ui/EmptyState';
import { SelectField } from '@/components/ui/Fields';
import { Link } from '@/components/ui/Link';
import { PageHeader } from '@/components/ui/PageHeader';
import {
  AREA_LABELS,
  useActivity,
  type ActivityArea,
  type ActivityFilters,
} from '@/features/activity/api';
import { useAuth } from '@/lib/auth-context';
import { formatDate, formatDateTime } from '@/lib/format';
import { can, P } from '@/lib/permissions';

const KEYS = ['client_id', 'person_id', 'area', 'since', 'until'] as const;

export function Component() {
  const { actor } = useAuth();
  const [params, setParams] = useSearchParams();
  const filters = useMemo(() => {
    const out: ActivityFilters = {};
    for (const key of KEYS) {
      const value = params.get(key);
      if (value) (out as Record<string, string>)[key] = value;
    }
    return out;
  }, [params]);
  const activity = useActivity(filters);
  const pages = activity.data?.pages ?? [];
  const items = pages.flatMap((p) => p.items);
  const people = pages[0]?.people ?? [];
  const clients = useMemo(() => {
    const seen = new Map<string, string>();
    for (const i of items) seen.set(i.client.id, i.client.name);
    return [...seen]
      .map(([value, label]) => ({ value, label }))
      .sort((a, b) => a.label.localeCompare(b.label));
  }, [items]);
  const set = (key: (typeof KEYS)[number]) => (e: { target: { value: string } }) =>
    setParams((current) => {
      const next = new URLSearchParams(current);
      if (e.target.value) next.set(key, e.target.value);
      else next.delete(key);
      return next;
    });

  // Group by day for scanning.
  const days = new Map<string, typeof items>();
  for (const item of items) {
    // Group by the viewer's local calendar day (timestamps are UTC).
    const at = new Date(item.occurred_at);
    const day = `${at.getFullYear()}-${String(at.getMonth() + 1).padStart(2, '0')}-${String(at.getDate()).padStart(2, '0')}`;
    days.set(day, [...(days.get(day) ?? []), item]);
  }

  return (
    <>
      <PageHeader
        title="Activity log"
        description={
          <>
            Everything that happened on the clients you can see, newest first.
            {can(actor?.permissions ?? [], P.orgAuditView) ? (
              <>
                {' '}
                Organisation changes are in the{' '}
                <Link className="link" to="/team/teams?tab=audit">
                  organisation audit log
                </Link>
                .
              </>
            ) : null}
          </>
        }
      />
      <Panel flush>
        <div
          className="grid gap-3 border-b border-line-soft p-4 sm:grid-cols-2 xl:grid-cols-5"
          aria-label="Activity filters"
        >
          <SelectField
            label="Client"
            placeholder="All clients"
            value={filters.client_id ?? ''}
            onChange={set('client_id')}
            options={
              filters.client_id && !clients.some((c) => c.value === filters.client_id)
                ? [{ value: filters.client_id, label: 'Selected client' }, ...clients]
                : clients
            }
          />
          <SelectField
            label="Person"
            placeholder="Anyone"
            value={filters.person_id ?? ''}
            onChange={set('person_id')}
            options={people.map((p) => ({ value: p.id, label: p.full_name }))}
          />
          <SelectField
            label="Area"
            placeholder="Everything"
            value={filters.area ?? ''}
            onChange={set('area')}
            options={(Object.keys(AREA_LABELS) as ActivityArea[]).map((a) => ({
              value: a,
              label: AREA_LABELS[a],
            }))}
          />
          <div className="label">
            <label htmlFor="activity-since">From</label>
            <input
              id="activity-since"
              type="date"
              className="input"
              value={filters.since ?? ''}
              onChange={set('since')}
            />
          </div>
          <div className="label">
            <label htmlFor="activity-until">To</label>
            <input
              id="activity-until"
              type="date"
              className="input"
              value={filters.until ?? ''}
              onChange={set('until')}
            />
          </div>
        </div>
        {activity.isPending ? <EmptyState title="Loading…" /> : null}
        {!activity.isPending && !items.length ? (
          <EmptyState title="Nothing here yet" description="Try other filters." />
        ) : null}
        {items.length ? (
          <div data-testid="activity-log">
            {[...days].map(([day, entries]) => (
              <section key={day} aria-label={formatDate(day)}>
                <h2 className="sticky top-0 border-b border-line-soft bg-sunk px-5 py-1.5 text-[12px] font-semibold text-muted">
                  {formatDate(day)}
                </h2>
                <ul className="divide-y divide-line-soft">
                  {entries.map((item) => (
                    <li
                      key={item.id}
                      className="flex flex-wrap items-start gap-x-3 gap-y-1 px-5 py-2.5"
                    >
                      <Badge tone="neutral" className="mt-0.5">
                        {AREA_LABELS[item.area]}
                      </Badge>
                      <div className="min-w-0 flex-1">
                        <p className="text-[13.5px]">
                          {item.summary ?? item.verb.replace(/_/g, ' ')}
                        </p>
                        <p className="text-xs text-muted">
                          <Link className="link" to={`/clients/${item.client.id}`}>
                            {item.client.name}
                          </Link>{' '}
                          — {item.actor?.full_name ?? 'System'} · {formatDateTime(item.occurred_at)}
                        </p>
                      </div>
                    </li>
                  ))}
                </ul>
              </section>
            ))}
          </div>
        ) : null}
        {activity.hasNextPage ? (
          <div className="border-t border-line-soft p-3 text-center">
            <Button
              onClick={() => void activity.fetchNextPage()}
              disabled={activity.isFetchingNextPage}
            >
              {activity.isFetchingNextPage ? 'Loading…' : 'Load older activity'}
            </Button>
          </div>
        ) : null}
      </Panel>
    </>
  );
}
