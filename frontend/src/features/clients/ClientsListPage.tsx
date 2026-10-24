/**
 * Screen 1 – Client List (product mockup): search, status tabs with counts, client
 * logo + website, status pill, Account Manager, onboarding progress, last
 * activity, row actions, numbered pagination. Search/tab/page live in the URL.
 */
import { ChevronLeft, ChevronRight, Plus, Search } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router';

import { Avatar } from '@/components/ui/Avatar';
import { Badge } from '@/components/ui/Badge';
import { LinkButton } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Progress } from '@/components/ui/Data';
import { EmptyState } from '@/components/ui/EmptyState';
import { Link } from '@/components/ui/Link';
import { Menu } from '@/components/ui/Menu';
import { PageHeader } from '@/components/ui/PageHeader';
import { useToast } from '@/components/ui/Toast';
import {
  STATUS_TONE,
  useChangeClientStatus,
  useClientCounts,
  useClients,
  type ClientListItem,
  type ClientStatus,
} from '@/features/clients/api';
import { useOnboardingBoard } from '@/features/onboarding/api';
import { ApiError } from '@/lib/api-client';
import { useAuth } from '@/lib/auth-context';
import { timeAgo } from '@/lib/format';
import { can, P } from '@/lib/permissions';
import { cn } from '@/lib/utils';

export { STATUS_TONE } from '@/features/clients/api';

const PAGE_SIZE = 10;

const TABS: { key: ClientStatus | 'all'; label: string }[] = [
  { key: 'all', label: 'All Clients' },
  { key: 'onboarding', label: 'Onboarding' },
  { key: 'active', label: 'Active' },
  { key: 'on_hold', label: 'On Hold' },
  { key: 'completed', label: 'Completed' },
];

function progressTone(status: ClientStatus, value: number) {
  if (status === 'on_hold') return 'bad' as const;
  if (value >= 100) return 'ok' as const;
  if (value < 30) return 'warn' as const;
  return 'accent' as const;
}

function RowActions({ client }: { client: ClientListItem }) {
  const change = useChangeClientStatus(client.id);
  const { toast } = useToast();
  const run = async (action: 'hold' | 'complete' | 'reactivate', done: string) => {
    try {
      await change.mutateAsync(action);
      toast({ title: done });
    } catch (error) {
      toast({
        title: error instanceof ApiError ? error.message : 'Something went wrong. Try again.',
        tone: 'error',
      });
    }
  };
  return (
    <Menu
      label={`Actions for ${client.name}`}
      items={[
        { label: 'View profile', to: `/clients/${client.id}` },
        { label: 'Edit client', to: `/clients/${client.id}/edit` },
        { label: 'Onboarding checklist', to: `/clients/${client.id}/summary` },
        {
          label: 'Put on hold',
          hidden: !['onboarding', 'active'].includes(client.status),
          onSelect: () => void run('hold', `${client.name} is on hold.`),
        },
        {
          label: 'Mark completed',
          hidden: client.status !== 'active',
          onSelect: () => void run('complete', `${client.name} marked completed.`),
        },
        {
          label: 'Reactivate',
          hidden: !['on_hold', 'completed'].includes(client.status),
          onSelect: () => void run('reactivate', `${client.name} reactivated.`),
        },
      ]}
    />
  );
}

function pageNumbers(current: number, last: number): (number | '…')[] {
  if (last <= 5) return Array.from({ length: last }, (_, i) => i + 1);
  const pages = new Set(
    [1, last, current - 1, current, current + 1].filter((p) => p >= 1 && p <= last),
  );
  const sorted = [...pages].sort((a, b) => a - b);
  const out: (number | '…')[] = [];
  sorted.forEach((p, i) => {
    if (i && p - sorted[i - 1]! > 1) out.push('…');
    out.push(p);
  });
  return out;
}

export function Component() {
  const { actor } = useAuth();
  const canCreate = can(actor?.permissions ?? [], P.clientsCreate);
  const [params, setParams] = useSearchParams();
  const q = params.get('q') ?? '';
  const tab = (params.get('status') as ClientStatus | null) ?? 'all';
  const page = Math.max(1, Number(params.get('page') ?? '1') || 1);

  const update = (changes: Record<string, string | null>) =>
    setParams((current) => {
      const next = new URLSearchParams(current);
      for (const [key, value] of Object.entries(changes)) {
        if (value) next.set(key, value);
        else next.delete(key);
      }
      return next;
    });

  const [draft, setDraft] = useState(q);
  useEffect(() => {
    if (draft === q) return;
    const timer = window.setTimeout(() => update({ q: draft.trim() || null, page: null }), 300);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draft, q]);

  const clients = useClients({
    q: q || undefined,
    status: tab === 'all' ? undefined : tab,
    page,
    page_size: PAGE_SIZE,
    sort: '-created_at',
  });
  const counts = useClientCounts();
  const board = useOnboardingBoard();
  const progress = useMemo(
    () => new Map((board.data ?? []).map((row) => [row.client_id, row.progress])),
    [board.data],
  );
  const data = clients.data;
  const last = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
  const from = data && data.total ? (data.page - 1) * data.page_size + 1 : 0;
  const to = data ? Math.min(data.page * data.page_size, data.total) : 0;

  return (
    <>
      <PageHeader title="Client List" />
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <label className="relative w-full max-w-[360px]">
          <span className="sr-only">Search clients</span>
          <Search
            aria-hidden
            className="pointer-events-none absolute top-1/2 left-3.5 size-4 -translate-y-1/2 text-muted"
          />
          <input
            type="search"
            className="input w-full py-2.5 pl-10"
            placeholder="Search clients..."
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
          />
        </label>
        {canCreate ? (
          <LinkButton to="/clients/new" variant="primary" className="px-5 py-2.5">
            <Plus aria-hidden className="size-4" />
            New Client
          </LinkButton>
        ) : null}
      </div>

      <div
        role="tablist"
        aria-label="Client status"
        className="mb-5 flex gap-1 overflow-x-auto border-b border-line"
      >
        {TABS.map((t) => {
          const count = t.key === 'all' ? undefined : counts.data?.[t.key];
          return (
            <button
              key={t.key}
              type="button"
              role="tab"
              aria-selected={tab === t.key}
              onClick={() => update({ status: t.key === 'all' ? null : t.key, page: null })}
              className={cn(
                '-mb-px cursor-pointer border-b-2 px-5 py-3 text-sm font-medium whitespace-nowrap',
                tab === t.key
                  ? 'border-accent text-accent'
                  : 'border-transparent text-muted hover:text-fg',
              )}
            >
              {t.label}
              {count !== undefined ? ` (${count})` : ''}
            </button>
          );
        })}
      </div>

      <Card className="overflow-hidden">
        {clients.isPending ? <EmptyState title="Loading clients…" /> : null}
        {clients.isError ? (
          <EmptyState title="Couldn't load clients" description="Reload the page to try again." />
        ) : null}
        {data && data.total === 0 ? (
          <EmptyState
            title={q || tab !== 'all' ? 'No clients match' : 'No clients yet'}
            description={
              q || tab !== 'all'
                ? 'Try a different search or tab.'
                : 'Create the first client once the contract is signed. Onboarding starts automatically.'
            }
          />
        ) : null}
        {data && data.total > 0 ? (
          <div className="overflow-x-auto">
            <table className="table" data-testid="clients-table">
              <thead>
                <tr>
                  <th>Client</th>
                  <th>Status</th>
                  <th>Account Manager</th>
                  <th className="min-w-[200px]">Progress</th>
                  <th>Last Activity</th>
                  <th className="text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((client) => {
                  const value =
                    progress.get(client.id) ??
                    (client.status === 'active' || client.status === 'completed' ? 100 : 0);
                  return (
                    <tr key={client.id}>
                      <td>
                        <div className="flex items-center gap-3.5">
                          <Avatar name={client.name} size="md" />
                          <div className="min-w-0">
                            <Link
                              className="font-semibold text-fg hover:text-accent"
                              to={`/clients/${client.id}`}
                            >
                              {client.name}
                            </Link>
                            <div className="truncate text-[13px] text-muted">
                              {client.website ?? client.code}
                            </div>
                          </div>
                        </div>
                      </td>
                      <td>
                        <Badge tone={STATUS_TONE[client.status]}>{client.status_label}</Badge>
                      </td>
                      <td>
                        <span className="flex items-center gap-2.5">
                          <Avatar name={client.account_manager.full_name} size="sm" />
                          {client.account_manager.full_name}
                        </span>
                      </td>
                      <td>
                        <Progress
                          value={value}
                          tone={progressTone(client.status, value)}
                          label={`${client.name} onboarding progress`}
                        />
                      </td>
                      <td className="whitespace-nowrap text-muted">
                        {timeAgo(client.last_activity_at)}
                      </td>
                      <td className="text-right">
                        <RowActions client={client} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : null}
        {data && data.total > 0 ? (
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line-soft px-5 py-4 text-[13px] text-muted">
            <span>
              Showing {from} to {to} of {data.total} clients
            </span>
            <nav aria-label="Pages" className="flex items-center gap-2">
              <button
                type="button"
                aria-label="Previous page"
                disabled={page <= 1}
                onClick={() => update({ page: String(page - 1) })}
                className="grid size-9 cursor-pointer place-items-center rounded-lg border border-line bg-surface disabled:opacity-40"
              >
                <ChevronLeft aria-hidden className="size-4" />
              </button>
              {pageNumbers(page, last).map((p, i) =>
                p === '…' ? (
                  <span key={`gap-${i}`} className="px-1">
                    …
                  </span>
                ) : (
                  <button
                    key={p}
                    type="button"
                    aria-current={p === page ? 'page' : undefined}
                    onClick={() => update({ page: p === 1 ? null : String(p) })}
                    className={cn(
                      'grid size-9 cursor-pointer place-items-center rounded-lg border text-sm font-medium',
                      p === page
                        ? 'border-accent bg-accent text-on-accent'
                        : 'border-line bg-surface text-fg',
                    )}
                  >
                    {p}
                  </button>
                ),
              )}
              <button
                type="button"
                aria-label="Next page"
                disabled={page >= last}
                onClick={() => update({ page: String(page + 1) })}
                className="grid size-9 cursor-pointer place-items-center rounded-lg border border-line bg-surface disabled:opacity-40"
              >
                <ChevronRight aria-hidden className="size-4" />
              </button>
            </nav>
          </div>
        ) : null}
      </Card>
    </>
  );
}
