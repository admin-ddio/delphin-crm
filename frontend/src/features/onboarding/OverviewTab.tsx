/**
 * Screen 3 – Client Profile Dashboard (product mockup): onboarding progress ring and
 * 6-stage tracker, client details, quick status, recent activity, next steps; plus
 * the review / completion actions and the "create the project" hand-off.
 */
import {
  Activity,
  CalendarCheck,
  CheckCircle2,
  ChevronRight,
  ChevronsRight,
  CircleAlert,
  CircleDashed,
  ClipboardList,
  FileText,
  Loader,
  Lock,
  Pencil,
  Target,
  UserCheck,
  UsersRound,
  type LucideIcon,
} from 'lucide-react';
import { useState } from 'react';

import { Alert } from '@/components/ui/Alert';
import { Badge } from '@/components/ui/Badge';
import { Button, LinkButton } from '@/components/ui/Button';
import { Card, Panel } from '@/components/ui/Card';
import { KeyValue, StepList } from '@/components/ui/Data';
import { Dialog } from '@/components/ui/Dialog';
import { EmptyState } from '@/components/ui/EmptyState';
import { Link } from '@/components/ui/Link';
import { Ring } from '@/components/ui/Ring';
import { useToast } from '@/components/ui/Toast';
import {
  labelOf,
  PAYMENT_TERMS,
  BUSINESS_TYPES,
  useClientActivity,
  type ClientDetail,
} from '@/features/clients/api';
import {
  onboardingApi,
  STAGE_STATE,
  useOnboarding,
  useOnboardingAction,
  type OnboardingDetail,
} from '@/features/onboarding/api';
import { useProjects } from '@/features/projects/api';
import { ApiError } from '@/lib/api-client';
import { useAuth } from '@/lib/auth-context';
import { countryName, flag } from '@/lib/countries';
import { formatDate, formatDateTime, formatINR } from '@/lib/format';
import { can, P } from '@/lib/permissions';
import { cn } from '@/lib/utils';

const STAGE_ICONS: Record<string, LucideIcon> = {
  client: UserCheck,
  questionnaire: ClipboardList,
  access: Lock,
  kpis: Target,
  kickoff: UsersRound,
  review: CheckCircle2,
};

const STAGE_STYLE = {
  completed: 'bg-ok text-white ring-ok/20',
  in_progress: 'bg-warn text-white ring-warn/20',
  blocked: 'bg-bad text-white ring-bad/20',
  pending: 'bg-sunk text-muted ring-line',
} as const;

const NEXT_ICONS: Record<string, LucideIcon> = {
  access_in: Lock,
  access_ok: Lock,
  kpi: Target,
  kickoff_client: CalendarCheck,
  kickoff_internal: UsersRound,
  q_sent: ClipboardList,
  q_done: ClipboardList,
};

const PRIORITY = {
  high: { label: 'High', tone: 'bad' },
  medium: { label: 'Medium', tone: 'warn' },
  low: { label: 'Low', tone: 'neutral' },
} as const;

function errorMessage(error: unknown) {
  return error instanceof ApiError ? error.message : 'Something went wrong. Try again.';
}

function ProgressCard({ data }: { data: OnboardingDetail }) {
  return (
    <Card className="flex flex-col gap-6 p-6 lg:flex-row lg:items-center" data-testid="onboarding">
      <Ring value={data.progress} size={128} label="Onboarding progress">
        <div>
          <div className="text-[26px] leading-none font-bold">{data.progress}%</div>
          <div className="mt-1 text-xs text-muted">Complete</div>
        </div>
      </Ring>
      <div className="min-w-0 flex-1">
        <h2 className="mb-5 text-base font-semibold">Onboarding Progress</h2>
        <ol className="flex flex-wrap items-start gap-y-5">
          {data.stages.map((stage, i) => {
            const Icon = STAGE_ICONS[stage.key] ?? CircleDashed;
            return (
              <li key={stage.key} className="flex min-w-[110px] flex-1 items-start">
                <div className="flex flex-1 flex-col items-center gap-2 text-center">
                  <span
                    className={cn(
                      'grid size-12 place-items-center rounded-full ring-4',
                      STAGE_STYLE[stage.state],
                    )}
                  >
                    <Icon aria-hidden className="size-5" />
                  </span>
                  <span className="text-sm font-medium">{stage.label}</span>
                  <span
                    className={cn(
                      'text-xs font-medium',
                      stage.state === 'completed' && 'text-ok',
                      stage.state === 'in_progress' && 'text-warn',
                      stage.state === 'blocked' && 'text-bad',
                      stage.state === 'pending' && 'text-muted',
                    )}
                  >
                    {STAGE_STATE[stage.state].label}
                  </span>
                </div>
                {i < data.stages.length - 1 ? (
                  <ChevronsRight aria-hidden className="mt-4 size-4 shrink-0 text-faint" />
                ) : null}
              </li>
            );
          })}
        </ol>
      </div>
    </Card>
  );
}

function ClientDetails({ client }: { client: ClientDetail }) {
  return (
    <Panel
      title="Client Details"
      icon={FileText}
      actions={
        client.can_edit ? (
          <LinkButton to={`/clients/${client.id}/edit`} size="sm">
            <Pencil aria-hidden className="size-3.5" />
            Edit Profile
          </LinkButton>
        ) : null
      }
    >
      <KeyValue
        items={[
          ['Account Manager', client.account_manager.full_name],
          [
            'Primary Contact',
            client.contact_name
              ? `${client.contact_name}${client.contact_designation ? ` (${client.contact_designation})` : ''}`
              : null,
          ],
          ['Email', client.contact_email],
          ['Phone', client.contact_phone],
          [
            'Contract Period',
            client.contract_start
              ? `${formatDate(client.contract_start)} – ${formatDate(client.contract_end)}`
              : null,
          ],
          ['Contract Value', client.contract_value ? formatINR(client.contract_value) : null],
          ['Payment Terms', labelOf(PAYMENT_TERMS, client.payment_terms)],
          ['Business Type', labelOf(BUSINESS_TYPES, client.business_type)],
          ['Industry', client.industry],
          [
            'Country',
            client.country ? `${flag(client.country)} ${countryName(client.country)}` : null,
          ],
          ['Notes', client.contract_notes],
        ]}
      />
    </Panel>
  );
}

const QUICK_ICON = {
  completed: <CheckCircle2 aria-hidden className="size-5 text-ok" />,
  in_progress: <Loader aria-hidden className="size-5 text-warn" />,
  blocked: <CircleAlert aria-hidden className="size-5 text-bad" />,
  pending: <CircleDashed aria-hidden className="size-5 text-muted" />,
} as const;

function QuickStatus({ data }: { data: OnboardingDetail }) {
  const [open, setOpen] = useState(false);
  return (
    <Panel title="Quick Status" icon={Activity}>
      <ul className="flex flex-col gap-3.5" data-testid="quick-status">
        {data.quick_status.map((item) => (
          <li key={item.key} className="flex items-center gap-3">
            {QUICK_ICON[item.state]}
            <span className="flex-1 text-sm font-medium">{item.label}</span>
            <Badge tone={STAGE_STATE[item.state].tone}>{STAGE_STATE[item.state].label}</Badge>
          </li>
        ))}
      </ul>
      <Button className="mt-5 w-full border-accent text-accent" onClick={() => setOpen(true)}>
        <ClipboardList aria-hidden className="size-4" />
        View Onboarding Checklist
      </Button>
      <Dialog open={open} onClose={() => setOpen(false)} title="Onboarding checklist (13 steps)">
        <StepList
          steps={data.steps.map((s) => ({
            label: s.label,
            state: s.state,
            detail: s.state === 'done' ? undefined : s.detail || s.hint,
          }))}
        />
      </Dialog>
    </Panel>
  );
}

function RecentActivity({ clientId }: { clientId: string }) {
  const activity = useClientActivity(clientId);
  const items = activity.data?.slice(0, 5) ?? [];
  return (
    <Panel
      title="Recent Activity"
      icon={Activity}
      actions={
        <Link className="link text-[13px]" to={`/clients/${clientId}/activity`}>
          View All
        </Link>
      }
    >
      {activity.data?.length === 0 ? <EmptyState title="No activity yet" /> : null}
      <ol className="flex flex-col">
        {items.map((entry, i) => (
          <li key={entry.id} className="relative flex gap-3 pb-4 last:pb-0">
            {i < items.length - 1 ? (
              <span aria-hidden className="absolute top-6 bottom-0 left-[9px] w-px bg-line" />
            ) : null}
            <CheckCircle2
              aria-hidden
              className="relative mt-0.5 size-5 shrink-0 bg-surface text-ok"
            />
            <div className="min-w-0">
              <div className="text-sm font-medium">{entry.summary}</div>
              <div className="text-xs text-muted">
                By {entry.actor?.full_name ?? 'the client'} · {formatDateTime(entry.occurred_at)}
              </div>
            </div>
          </li>
        ))}
      </ol>
    </Panel>
  );
}

function NextSteps({ data, clientId }: { data: OnboardingDetail; clientId: string }) {
  if (!data.next_actions.length) return null;
  return (
    <Panel
      title="Next Steps"
      icon={CalendarCheck}
      actions={
        <Link
          className="link inline-flex items-center gap-1 text-[13px]"
          to={`/clients/${clientId}/summary`}
        >
          View Full Checklist <ChevronRight aria-hidden className="size-4" />
        </Link>
      }
    >
      <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" data-testid="next-steps">
        {data.next_actions.map((action) => {
          const Icon = NEXT_ICONS[action.step] ?? ClipboardList;
          const priority = PRIORITY[action.priority];
          return (
            <li
              key={action.step}
              className="flex items-start gap-3 rounded-xl border border-line p-4"
            >
              <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-accent-soft text-accent">
                <Icon aria-hidden className="size-5" />
              </span>
              <div className="min-w-0 flex-1">
                <div className="text-sm font-semibold">{action.title}</div>
                <div className="mt-1 flex flex-wrap items-center justify-between gap-2 text-xs text-muted">
                  Due: {formatDate(action.due)}
                  <Badge tone={priority.tone}>{priority.label}</Badge>
                </div>
              </div>
            </li>
          );
        })}
      </ul>
    </Panel>
  );
}

function ReviewAndCompletion({ data, client }: { data: OnboardingDetail; client: ClientDetail }) {
  const { actor } = useAuth();
  const action = useOnboardingAction(client.id);
  const { toast } = useToast();
  const projects = useProjects(client.id);
  const run = async (call: () => Promise<OnboardingDetail>, done: string) => {
    try {
      await action.mutateAsync(call);
      toast({ title: done });
    } catch (error) {
      toast({ title: errorMessage(error), tone: 'error' });
    }
  };

  if (data.locked_reason && !data.completed_at) {
    return (
      <Alert tone="warn" title="Onboarding is paused">
        {data.locked_reason}
      </Alert>
    );
  }
  if (data.completed_at) {
    const hasProject = Boolean(projects.data?.length);
    return (
      <Alert tone="ok" title={`Onboarding completed ${formatDate(data.completed_at)}`}>
        The client is Active and project creation is enabled.{' '}
        {!hasProject && can(actor?.permissions ?? [], P.projectsCreate) ? (
          <Link className="link" to={`/projects/new?client=${client.id}`}>
            Create the delivery project →
          </Link>
        ) : null}
      </Alert>
    );
  }
  if (!data.permissions.manage) return null;
  const ready = data.steps.slice(0, 10).every((s) => s.state === 'done');
  return (
    <Card className="flex flex-wrap items-center justify-between gap-3 px-5 py-4">
      <div>
        <div className="text-sm font-semibold">Onboarding review &amp; completion</div>
        <div className="text-[13px] text-muted">
          The review passes once steps 1–10 are done. Completion re-checks that every access item is
          verified and every KPI is client-confirmed.
        </div>
      </div>
      <div className="flex gap-2">
        <Button
          disabled={action.isPending || Boolean(data.reviewed_at) || !ready}
          onClick={() =>
            void run(() => onboardingApi.review(client.id), 'Onboarding review passed.')
          }
        >
          {data.reviewed_at ? 'Review passed ✓' : 'Pass onboarding review'}
        </Button>
        <Button
          variant="primary"
          disabled={action.isPending}
          onClick={() =>
            void run(
              () => onboardingApi.complete(client.id),
              'Onboarding completed — the client is Active.',
            )
          }
        >
          Complete onboarding
        </Button>
      </div>
    </Card>
  );
}

export function OverviewTab({ client }: { client: ClientDetail }) {
  const onboarding = useOnboarding(client.id);
  const data = onboarding.data;
  if (onboarding.isPending) return <EmptyState title="Loading onboarding…" />;
  if (!data)
    return (
      <EmptyState title="Couldn't load onboarding" description="Reload the page to try again." />
    );
  return (
    <div className="flex flex-col gap-5">
      <ProgressCard data={data} />
      <ReviewAndCompletion data={data} client={client} />
      <div className="grid items-start gap-5 xl:grid-cols-[1.25fr_1fr_1fr]">
        <ClientDetails client={client} />
        <QuickStatus data={data} />
        <RecentActivity clientId={client.id} />
      </div>
      <NextSteps data={data} clientId={client.id} />
    </div>
  );
}
