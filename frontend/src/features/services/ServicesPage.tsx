/**
 * /services: Services & retainers. Tiles (Contracted / month for money roles only),
 * then Retainers (SEO, Social Media: this month's progress) and Projects (Website,
 * Web App, Mobile App: delivery progress). Scoped to clients the viewer can see.
 */
import { CalendarClock, FolderKanban, Hourglass, IndianRupee } from 'lucide-react';
import { useSearchParams } from 'react-router';

import { Badge } from '@/components/ui/Badge';
import { LinkButton } from '@/components/ui/Button';
import { Panel, StatCard } from '@/components/ui/Card';
import { Progress, Tabs } from '@/components/ui/Data';
import { EmptyState } from '@/components/ui/EmptyState';
import { SelectField } from '@/components/ui/Fields';
import { Link } from '@/components/ui/Link';
import { PageHeader } from '@/components/ui/PageHeader';
import {
  SERVICE_STATUS,
  formatMoney,
  useServices,
  type ServiceItem,
  type ServiceKind,
  type ServiceStatus,
} from '@/features/services/api';
import { useAuth } from '@/lib/auth-context';
import { can, P } from '@/lib/permissions';
import { formatDate } from '@/lib/format';

function pct(item: ServiceItem) {
  return item.progress.total ? Math.round((item.progress.done * 100) / item.progress.total) : 0;
}

function Table({
  items,
  kind,
  money,
}: {
  items: ServiceItem[];
  kind: ServiceKind;
  money: boolean;
}) {
  if (!items.length) {
    return (
      <EmptyState
        title={kind === 'retainer' ? 'No retainers' : 'No projects'}
        description="Services are chosen when a client is created, or added from the client profile."
      />
    );
  }
  return (
    <div className="overflow-x-auto">
      <table className="table" data-testid={`${kind}-table`}>
        <thead>
          <tr>
            <th>Client</th>
            <th>Service</th>
            <th>Status</th>
            <th>Project Manager</th>
            <th>{kind === 'retainer' ? 'Since' : 'Started'}</th>
            <th>{kind === 'retainer' ? 'This month' : 'Delivery'}</th>
            {money ? (
              <th className="text-right">{kind === 'retainer' ? 'Monthly fee' : 'Value'}</th>
            ) : null}
          </tr>
        </thead>
        <tbody>
          {items.map((s) => (
            <tr key={s.id}>
              <td>
                <Link className="link font-medium" to={`/clients/${s.client.id}`}>
                  {s.client.name}
                </Link>
                <div className="code">{s.client.code}</div>
              </td>
              <td>
                <Link className="link" to={`/services/${s.id}`}>
                  {s.service.name}
                </Link>
                <div className="code">{s.code}</div>
              </td>
              <td>
                <Badge tone={SERVICE_STATUS[s.status].tone}>{s.status_label}</Badge>
              </td>
              <td>{s.manager?.full_name ?? <span className="text-muted">—</span>}</td>
              <td>
                {s.start_date ? (
                  formatDate(s.start_date)
                ) : (
                  <span className="text-muted">Not started</span>
                )}
              </td>
              <td className="min-w-40">
                {s.progress.total ? (
                  <Progress
                    value={pct(s)}
                    label={`${s.progress.done} of ${s.progress.total} tasks done`}
                  />
                ) : (
                  <span className="text-muted">—</span>
                )}
              </td>
              {money ? (
                <td className="text-right tabular-nums">
                  {formatMoney(s.fee, s.currency) ?? <span className="text-muted">—</span>}
                </td>
              ) : null}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Component() {
  const { actor } = useAuth();
  const granted = actor?.permissions ?? [];
  const [params, setParams] = useSearchParams();
  const kind = (params.get('kind') as ServiceKind | null) ?? 'retainer';
  const status = (params.get('status') as ServiceStatus | null) ?? undefined;
  const services = useServices({ status });
  const money = can(granted, P.financeView);
  const tiles = services.data?.tiles;
  const items = (services.data?.items ?? []).filter((s) => s.service.kind === kind);
  const set = (key: string, value: string) =>
    setParams((current) => {
      const next = new URLSearchParams(current);
      if (value) next.set(key, value);
      else next.delete(key);
      return next;
    });

  return (
    <>
      <PageHeader
        title="Services & retainers"
        description="Monthly SEO and Social Media retainers, and Website, Web App and Mobile App projects."
        actions={
          can(granted, P.servicesTemplatesManage) ? (
            <LinkButton to="/services/templates">Service templates</LinkButton>
          ) : null
        }
      />
      <div className="mb-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-4" data-testid="services-tiles">
        <StatCard
          icon={CalendarClock}
          tone="accent"
          label="Active retainers"
          value={tiles?.active_retainers ?? '—'}
        />
        <StatCard
          icon={FolderKanban}
          tone="info"
          label="Projects in progress"
          value={tiles?.projects_in_progress ?? '—'}
        />
        <StatCard
          icon={Hourglass}
          tone="warn"
          label="Not started yet"
          value={tiles?.planned ?? '—'}
        />
        {money ? (
          <StatCard
            icon={IndianRupee}
            tone="ok"
            label="Contracted / month"
            value={formatMoney(tiles?.contracted_monthly) ?? '—'}
            hint="Active retainer fees (contracted value, not revenue)"
          />
        ) : null}
      </div>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <Tabs
          label="Service kind"
          value={kind}
          onChange={(key) => set('kind', key === 'retainer' ? '' : key)}
          items={[
            { key: 'retainer', label: 'Retainers' },
            { key: 'project', label: 'Projects' },
          ]}
        />
        <div className="mb-3 w-44">
          <SelectField
            label="Status"
            placeholder="Any status"
            value={status ?? ''}
            onChange={(e) => set('status', e.target.value)}
            options={Object.entries(SERVICE_STATUS).map(([value, st]) => ({
              value,
              label: st.label,
            }))}
          />
        </div>
      </div>
      <Panel flush>
        {services.isPending ? (
          <EmptyState title="Loading…" />
        ) : (
          <Table items={items} kind={kind} money={money} />
        )}
      </Panel>
    </>
  );
}
