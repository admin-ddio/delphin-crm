/**
 * A client's services on the client profile: what was bought, their state, and
 * Start (after onboarding) / Add services for the client's Account Manager.
 */
import { Briefcase } from 'lucide-react';
import { useId, useState, type FormEvent } from 'react';

import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Panel } from '@/components/ui/Card';
import { Dialog } from '@/components/ui/Dialog';
import { EmptyState } from '@/components/ui/EmptyState';
import { Link } from '@/components/ui/Link';
import { useToast } from '@/components/ui/Toast';
import type { ClientDetail } from '@/features/clients/api';
import {
  SERVICE_STATUS,
  formatMoney,
  useAddServices,
  useServices,
  useStartOptions,
  useStartService,
  type ServiceItem,
} from '@/features/services/api';
import { ServicePicker, toSelections, type ServiceChoice } from '@/features/services/ServicePicker';
import { ApiError } from '@/lib/api-client';
import { useAuth } from '@/lib/auth-context';
import { can, P } from '@/lib/permissions';

function errorMessage(error: unknown) {
  return error instanceof ApiError ? error.message : 'Something went wrong. Try again.';
}

function today() {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

export function StartServiceDialog({
  service,
  onClose,
}: {
  service: ServiceItem;
  onClose(): void;
}) {
  const options = useStartOptions(service.id);
  const start = useStartService(service.id);
  const { toast } = useToast();
  const ids = { manager: useId(), date: useId() };
  const [manager, setManager] = useState<string | null>(null);
  const [startDate, setStartDate] = useState(today());
  const chosen = manager ?? options.data?.default_manager?.id ?? '';

  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      const detail = await start.mutateAsync({ manager_id: chosen, start_date: startDate });
      toast({
        title: `${service.service.name} started. Project ${detail.project?.code ?? ''} is ready.`,
      });
      onClose();
    } catch (error) {
      toast({ title: errorMessage(error), tone: 'error' });
    }
  }

  return (
    <Dialog open onClose={onClose} title={`Start ${service.service.name}`}>
      <form className="flex flex-col gap-3" onSubmit={submit}>
        <p className="text-[13px] text-muted">
          {service.service.kind === 'retainer'
            ? 'Creates the delivery project with the setup tasks. Monthly tasks follow from next month.'
            : 'Creates the delivery project with every phase, dated from the start date.'}
        </p>
        <div className="label">
          <label htmlFor={ids.manager}>Project Manager *</label>
          <select
            id={ids.manager}
            className="input"
            required
            value={chosen}
            onChange={(e) => setManager(e.target.value)}
          >
            <option value="">Choose…</option>
            {options.data?.managers.map((m) => (
              <option key={m.id} value={m.id}>
                {m.full_name}
                {m.id === options.data?.default_manager?.id ? ' (department default)' : ''}
              </option>
            ))}
          </select>
        </div>
        <div className="label">
          <label htmlFor={ids.date}>Start date *</label>
          <input
            id={ids.date}
            type="date"
            className="input"
            required
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
          />
        </div>
        <div className="flex justify-end gap-2">
          <Button type="button" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" disabled={!chosen || start.isPending}>
            Start service
          </Button>
        </div>
      </form>
    </Dialog>
  );
}

function AddServicesDialog({
  client,
  existing,
  onClose,
}: {
  client: ClientDetail;
  existing: ServiceItem[];
  onClose(): void;
}) {
  const add = useAddServices(client.id);
  const { actor } = useAuth();
  const { toast } = useToast();
  const [choice, setChoice] = useState<ServiceChoice>({});
  const open = existing
    .filter(
      (s) => s.service.kind === 'retainer' && ['planned', 'active', 'paused'].includes(s.status),
    )
    .map((s) => s.service.key);

  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      await add.mutateAsync(toSelections(choice));
      toast({ title: 'Services added.' });
      onClose();
    } catch (error) {
      toast({ title: errorMessage(error), tone: 'error' });
    }
  }

  return (
    <Dialog open onClose={onClose} title={`Add services: ${client.name}`}>
      <form className="flex flex-col gap-4" onSubmit={submit}>
        <ServicePicker
          value={choice}
          onChange={setChoice}
          exclude={open}
          showFees={can(actor?.permissions ?? [], P.financeView)}
        />
        <div className="flex justify-end gap-2">
          <Button type="button" onClick={onClose}>
            Cancel
          </Button>
          <Button
            type="submit"
            variant="primary"
            disabled={!Object.keys(choice).length || add.isPending}
          >
            Add services
          </Button>
        </div>
      </form>
    </Dialog>
  );
}

export function ClientServicesPanel({
  client,
  onboardingCompleted,
}: {
  client: ClientDetail;
  onboardingCompleted: boolean;
}) {
  const { actor } = useAuth();
  const services = useServices({ client_id: client.id });
  const [starting, setStarting] = useState<ServiceItem | null>(null);
  const [adding, setAdding] = useState(false);
  const granted = actor?.permissions ?? [];
  const manage =
    can(granted, P.servicesManage) &&
    (granted.includes('*') || client.account_manager.id === actor?.id);
  const items = services.data?.items ?? [];

  return (
    <div id="client-services-panel">
      <Panel
        title="Services"
        icon={Briefcase}
        description={
          onboardingCompleted
            ? 'Start each service to create its delivery project.'
            : 'Services start once onboarding is completed.'
        }
        flush
        actions={
          manage ? (
            <Button size="sm" onClick={() => setAdding(true)}>
              Add services
            </Button>
          ) : null
        }
      >
        {services.isPending ? <EmptyState title="Loading…" /> : null}
        {!services.isPending && !items.length ? (
          <EmptyState title="No services yet" description="Add the services this client bought." />
        ) : null}
        {items.length ? (
          <ul className="divide-y divide-line-soft" data-testid="client-services">
            {items.map((s) => (
              <li key={s.id} className="flex flex-wrap items-center gap-3 px-5 py-3">
                <div className="min-w-48 flex-1">
                  <Link className="link font-medium" to={`/services/${s.id}`}>
                    {s.service.name}
                  </Link>{' '}
                  <span className="code">{s.code}</span>
                  <div className="text-xs text-muted">
                    {s.service.kind === 'retainer' ? 'Monthly retainer' : 'Project'}
                    {s.fee
                      ? ` · ${formatMoney(s.fee, s.currency)}${s.service.kind === 'retainer' ? '/month' : ''}`
                      : ''}
                    {s.manager ? ` · PM ${s.manager.full_name}` : ''}
                  </div>
                </div>
                <Badge tone={SERVICE_STATUS[s.status].tone}>{s.status_label}</Badge>
                {s.project ? (
                  <Link className="link text-[13px]" to={`/projects/${s.project.id}`}>
                    {s.project.code}
                  </Link>
                ) : null}
                {manage && s.status === 'planned' ? (
                  <Button
                    size="sm"
                    variant="primary"
                    disabled={!onboardingCompleted}
                    title={onboardingCompleted ? undefined : 'Complete onboarding first'}
                    onClick={() => setStarting(s)}
                  >
                    Start
                  </Button>
                ) : null}
              </li>
            ))}
          </ul>
        ) : null}
      </Panel>
      {starting ? (
        <StartServiceDialog service={starting} onClose={() => setStarting(null)} />
      ) : null}
      {adding ? (
        <AddServicesDialog client={client} existing={items} onClose={() => setAdding(false)} />
      ) : null}
    </div>
  );
}
