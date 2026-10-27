/**
 * /services/:id: the service workspace. Retainers: this month's tasks, monthly
 * history and "Generate this month"; projects: the delivery phases. Lifecycle
 * (start, pause, resume, complete, cancel) for the client's Account Manager.
 */
import { useState } from 'react';
import { useParams } from 'react-router';

import { Alert } from '@/components/ui/Alert';
import { Badge } from '@/components/ui/Badge';
import { Button, LinkButton } from '@/components/ui/Button';
import { Panel, StatCard } from '@/components/ui/Card';
import { KeyValue, Progress } from '@/components/ui/Data';
import { EmptyState } from '@/components/ui/EmptyState';
import { Link } from '@/components/ui/Link';
import { PageHeader } from '@/components/ui/PageHeader';
import { useToast } from '@/components/ui/Toast';
import { TaskDrawer } from '@/features/tasks/TaskDrawer';
import { TaskTable } from '@/features/tasks/TaskTable';
import {
  SERVICE_STATUS,
  formatMoney,
  useGenerateMonth,
  useService,
  useServiceAction,
  type ServiceAction,
  type ServiceDetail,
} from '@/features/services/api';
import { StartServiceDialog } from '@/features/services/ClientServicesPanel';
import { ApiError } from '@/lib/api-client';
import { formatDate } from '@/lib/format';

const crumb = { label: 'Services & retainers', to: '/services' };

function monthLabel(period: string) {
  const [year, month] = period.split('-').map(Number);
  return new Date(Date.UTC(year ?? 2000, (month ?? 1) - 1, 1)).toLocaleDateString('en-GB', {
    month: 'long',
    year: 'numeric',
    timeZone: 'UTC',
  });
}

const ACTIONS: Record<ServiceDetail['status'], { action: ServiceAction; label: string }[]> = {
  planned: [{ action: 'cancel', label: 'Cancel' }],
  active: [
    { action: 'pause', label: 'Pause' },
    { action: 'complete', label: 'Complete' },
    { action: 'cancel', label: 'Cancel' },
  ],
  paused: [
    { action: 'resume', label: 'Resume' },
    { action: 'complete', label: 'Complete' },
    { action: 'cancel', label: 'Cancel' },
  ],
  completed: [],
  cancelled: [],
};

function Actions({ service }: { service: ServiceDetail }) {
  const act = useServiceAction(service.id);
  const generate = useGenerateMonth(service.id);
  const { toast } = useToast();
  const [starting, setStarting] = useState(false);
  const run = async (action: ServiceAction, label: string) => {
    if (
      (action === 'cancel' || action === 'complete') &&
      !window.confirm(`${label} ${service.service.name} for ${service.client.name}?`)
    )
      return;
    try {
      await act.mutateAsync(action);
      toast({ title: `${service.service.name}: ${label.toLowerCase()}d.` });
    } catch (error) {
      toast({
        title: error instanceof ApiError ? error.message : 'Something went wrong.',
        tone: 'error',
      });
    }
  };
  return (
    <div className="flex flex-wrap gap-2">
      {service.permissions.generate ? (
        <Button
          variant="primary"
          disabled={generate.isPending}
          onClick={async () => {
            try {
              const result = await generate.mutateAsync();
              toast({
                title: result.created
                  ? `${result.created} tasks created for ${monthLabel(result.period)}.`
                  : result.skipped
                    ? `${monthLabel(result.period)} is already generated.`
                    : 'Monthly tasks start the month after the retainer starts.',
              });
            } catch (error) {
              toast({
                title: error instanceof ApiError ? error.message : 'Something went wrong.',
                tone: 'error',
              });
            }
          }}
        >
          Generate this month
        </Button>
      ) : null}
      {service.permissions.manage && service.status === 'planned' ? (
        <Button
          variant="primary"
          disabled={!service.onboarding_completed}
          title={service.onboarding_completed ? undefined : 'Complete onboarding first'}
          onClick={() => setStarting(true)}
        >
          Start service
        </Button>
      ) : null}
      {service.permissions.manage
        ? ACTIONS[service.status].map((a) => (
            <Button
              key={a.action}
              disabled={act.isPending}
              onClick={() => void run(a.action, a.label)}
            >
              {a.label}
            </Button>
          ))
        : null}
      {starting ? (
        <StartServiceDialog service={service} onClose={() => setStarting(false)} />
      ) : null}
    </div>
  );
}

export function Component() {
  const { id = '' } = useParams();
  const query = useService(id);
  const [open, setOpen] = useState<string | null>(null);
  if (query.isPending) return <PageHeader title="Loading…" crumb={crumb} />;
  const service = query.data;
  if (!service) {
    return (
      <>
        <PageHeader title="Service not found" crumb={crumb} />
        <Alert tone="bad">This service doesn't exist or you don't have access to it.</Alert>
      </>
    );
  }
  const retainer = service.service.kind === 'retainer';
  const done = service.progress.total
    ? Math.round((service.progress.done * 100) / service.progress.total)
    : 0;

  return (
    <>
      <PageHeader
        crumb={crumb}
        title={
          <span className="flex flex-wrap items-center gap-2">
            {service.client.name}: {service.service.name}
            <Badge tone={SERVICE_STATUS[service.status].tone}>{service.status_label}</Badge>
          </span>
        }
        description={
          <>
            <span className="code">{service.code}</span> ·{' '}
            {retainer ? 'Monthly retainer' : 'Project'} ·{' '}
            <Link className="link" to={`/clients/${service.client.id}`}>
              {service.client.code}
            </Link>
          </>
        }
        actions={<Actions service={service} />}
      />
      {service.status === 'planned' && !service.onboarding_completed ? (
        <Alert tone="info" className="mb-4">
          This service starts once the client's onboarding is completed.
        </Alert>
      ) : null}
      <div className="grid items-start gap-5 xl:grid-cols-[1fr_2fr]">
        <div className="flex flex-col gap-5">
          <Panel title="Details">
            <KeyValue
              items={[
                ['Project Manager', service.manager?.full_name ?? 'Not started'],
                ['Started', service.start_date ? formatDate(service.start_date) : '—'],
                ['Ended', service.end_date ? formatDate(service.end_date) : '—'],
                [
                  'Project',
                  service.project ? (
                    <Link key="p" className="link" to={`/projects/${service.project.id}`}>
                      {service.project.code} · {service.project.name}
                    </Link>
                  ) : (
                    '—'
                  ),
                ],
                ...(service.permissions.see_money
                  ? ([
                      [
                        retainer ? 'Monthly fee' : 'Project value',
                        formatMoney(service.fee, service.currency) ?? '—',
                      ],
                    ] as [string, React.ReactNode][])
                  : []),
                ['Notes', service.notes],
              ]}
            />
          </Panel>
          {retainer ? (
            <Panel title="Monthly history" flush>
              {service.history.length ? (
                <table className="table" data-testid="service-history">
                  <thead>
                    <tr>
                      <th>Month</th>
                      <th>Done</th>
                    </tr>
                  </thead>
                  <tbody>
                    {service.history.map((m) => (
                      <tr key={m.period}>
                        <td>{monthLabel(m.period)}</td>
                        <td className="min-w-40">
                          <Progress
                            value={m.total ? (m.done * 100) / m.total : 0}
                            label={`${m.done} of ${m.total} tasks done`}
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <EmptyState
                  title="No months yet"
                  description="Monthly tasks start the month after the retainer starts."
                />
              )}
            </Panel>
          ) : (
            <StatCard
              label="Delivery progress"
              value={`${done}%`}
              hint={`${service.progress.done} of ${service.progress.total} phases done`}
            />
          )}
        </div>
        <Panel
          title={
            retainer
              ? `This month: ${service.current_period ? monthLabel(service.current_period) : ''}`
              : 'Delivery phases'
          }
          description={
            retainer
              ? 'Generated from the retainer template; reviews and client approvals follow the usual flow.'
              : 'From discovery to launch, dated from the start date.'
          }
          flush
          actions={
            service.project ? (
              <LinkButton size="sm" to={`/projects/${service.project.id}`}>
                Open project board
              </LinkButton>
            ) : null
          }
        >
          {service.tasks.length ? (
            <TaskTable tasks={service.tasks} onOpen={setOpen} />
          ) : (
            <EmptyState
              title={retainer ? 'No tasks this month yet' : 'Not started yet'}
              description={
                retainer
                  ? 'Use "Generate this month", or wait for the monthly job.'
                  : 'Start the service to create its delivery project.'
              }
            />
          )}
        </Panel>
      </div>
      <TaskDrawer taskId={open} onClose={() => setOpen(null)} />
    </>
  );
}
