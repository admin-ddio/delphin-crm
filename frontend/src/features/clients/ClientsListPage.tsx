/**
 * /clients: CRM & Clients list (layout and wording from the clickable demo).
 * Search, status filter and page live in the URL so the view is shareable.
 */
import { useEffect, useId, useState } from 'react';
import { useSearchParams } from 'react-router';

import { Badge, type BadgeTone } from '@/components/ui/Badge';
import { Button, LinkButton } from '@/components/ui/Button';
import { Panel } from '@/components/ui/Card';
import { EmptyState } from '@/components/ui/EmptyState';
import { Link } from '@/components/ui/Link';
import { PageHeader } from '@/components/ui/PageHeader';
import { STATUS_OPTIONS, useClients, type ClientStatus } from '@/features/clients/api';
import { useAuth } from '@/lib/auth-context';
import { formatDate } from '@/lib/format';
import { can, P } from '@/lib/permissions';

const PAGE_SIZE = 25;

export const STATUS_TONE: Record<ClientStatus, BadgeTone> = {
  contract_pending: 'neutral',
  onboarding: 'accent',
  active: 'ok',
};

export function Component() {
  const { actor } = useAuth();
  const canCreate = can(actor?.permissions ?? [], P.clientsCreate);
  const [params, setParams] = useSearchParams();
  const q = params.get('q') ?? '';
  const status = (params.get('status') as ClientStatus | null) ?? undefined;
  const page = Math.max(1, Number(params.get('page') ?? '1') || 1);
  const searchId = useId();
  const statusId = useId();

  // Debounce typing into the URL.
  const [draft, setDraft] = useState(q);
  useEffect(() => {
    if (draft === q) return;
    const timer = window.setTimeout(() => {
      setParams((current) => {
        const next = new URLSearchParams(current);
        if (draft.trim()) next.set('q', draft.trim());
        else next.delete('q');
        next.delete('page');
        return next;
      });
    }, 300);
    return () => window.clearTimeout(timer);
  }, [draft, q, setParams]);

  const clients = useClients({ q: q || undefined, status, page, page_size: PAGE_SIZE });
  const data = clients.data;
  const from = data && data.total ? (data.page - 1) * data.page_size + 1 : 0;
  const to = data ? Math.min(data.page * data.page_size, data.total) : 0;
  const filtered = Boolean(q || status);

  const setPage = (next: number) =>
    setParams((current) => {
      const updated = new URLSearchParams(current);
      updated.set('page', String(next));
      return updated;
    });

  const newClient = canCreate ? (
    <LinkButton to="/clients/new" variant="primary">
      New client
    </LinkButton>
  ) : null;

  return (
    <>
      <PageHeader
        title="CRM & Clients"
        description="Every client relationship. Lifecycle status is separate from onboarding progress."
        actions={newClient}
      />

      <div className="mb-3 flex flex-wrap items-end gap-3">
        <div className="label min-w-[240px] flex-1">
          <label htmlFor={searchId}>Search</label>
          <input
            id={searchId}
            type="search"
            className="input"
            placeholder="Name, code or domain"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
          />
        </div>
        <div className="label">
          <label htmlFor={statusId}>Status</label>
          <select
            id={statusId}
            className="input"
            value={status ?? ''}
            onChange={(event) =>
              setParams((current) => {
                const next = new URLSearchParams(current);
                if (event.target.value) next.set('status', event.target.value);
                else next.delete('status');
                next.delete('page');
                return next;
              })
            }
          >
            <option value="">All statuses</option>
            {STATUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <Panel flush>
        {clients.isPending ? <EmptyState title="Loading clients…" /> : null}
        {clients.isError ? (
          <EmptyState title="Couldn't load clients" description="Reload the page to try again." />
        ) : null}
        {data && data.total === 0 ? (
          filtered ? (
            <EmptyState title="No clients match" description="Try a different search or status." />
          ) : (
            <EmptyState
              title="No clients yet"
              description="Create the first client once the contract is signed. Onboarding starts automatically."
              action={
                newClient ?? (
                  <span className="text-muted">
                    Ask an Account Manager or Super Admin to create one.
                  </span>
                )
              }
            />
          )
        ) : null}
        {data && data.total > 0 ? (
          <div className="overflow-x-auto">
            <table className="table" data-testid="clients-table">
              <thead>
                <tr>
                  <th>Client</th>
                  <th>Status</th>
                  <th>Account Manager</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((client) => (
                  <tr key={client.id}>
                    <td>
                      <Link className="link" to={`/clients/${client.id}`}>
                        {client.name}
                      </Link>
                      <div className="code">
                        {client.code}
                        {client.domain ? ` · ${client.domain}` : ''}
                      </div>
                    </td>
                    <td>
                      <Badge tone={STATUS_TONE[client.status]}>{client.status_label}</Badge>
                    </td>
                    <td>{client.account_manager.full_name}</td>
                    <td className="font-mono text-xs tabular-nums">{formatDate(client.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </Panel>

      {data && data.total > data.page_size ? (
        <div className="mt-3 flex items-center justify-between gap-3 text-[13px] text-muted">
          <span>
            {from}–{to} of {data.total}
          </span>
          <div className="flex gap-2">
            <Button size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>
              Previous
            </Button>
            <Button size="sm" disabled={to >= data.total} onClick={() => setPage(page + 1)}>
              Next
            </Button>
          </div>
        </div>
      ) : null}
    </>
  );
}
