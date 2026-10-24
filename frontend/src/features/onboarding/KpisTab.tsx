/**
 * Screen 6 – KPI Targets (product mockup): totals (on track / at risk / behind),
 * metric table with baseline, target, target date, progress and status, overall
 * ring, notes, and the client-confirmation banner.
 */
import {
  AlarmClock,
  CircleCheck,
  Pencil,
  Plus,
  Target,
  TrendingDown,
  TrendingUp,
  UsersRound,
} from 'lucide-react';
import { useId, useState, type FormEvent } from 'react';

import { Alert } from '@/components/ui/Alert';
import { Avatar } from '@/components/ui/Avatar';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, Panel, StatCard } from '@/components/ui/Card';
import { Progress } from '@/components/ui/Data';
import { Dialog } from '@/components/ui/Dialog';
import { EmptyState } from '@/components/ui/EmptyState';
import { TextField } from '@/components/ui/Field';
import { SelectField, TextAreaField } from '@/components/ui/Fields';
import { Menu } from '@/components/ui/Menu';
import { Ring } from '@/components/ui/Ring';
import { useToast } from '@/components/ui/Toast';
import {
  CHANNELS,
  KPI_STATUS,
  onboardingApi,
  useOnboarding,
  useOnboardingAction,
  type ContactChannel,
  type Kpi,
  type OnboardingDetail,
} from '@/features/onboarding/api';
import { ApiError } from '@/lib/api-client';
import { formatDate } from '@/lib/format';

const num = (value: string | number | null | undefined) =>
  value === null || value === undefined
    ? '—'
    : Number(value).toLocaleString('en-IN', { maximumFractionDigits: 2 });

function months(from: string, to: string | null) {
  if (!to) return null;
  const m = Math.round((new Date(to).getTime() - new Date(from).getTime()) / (30.44 * 86_400_000));
  return m > 0 ? `${m} month${m === 1 ? '' : 's'}` : null;
}

function errorMessage(error: unknown) {
  return error instanceof ApiError ? error.message : 'Something went wrong. Try again.';
}

interface KpiFormValues {
  metric: string;
  description: string;
  baseline: string;
  target: string;
  unit: string;
  target_date: string;
  current_value: string;
}

function KpiDialog({
  clientId,
  kpi,
  mode,
  onClose,
}: {
  clientId: string;
  kpi: Kpi | null;
  mode: 'add' | 'edit' | 'current';
  onClose(): void;
}) {
  const action = useOnboardingAction(clientId);
  const { toast } = useToast();
  const formId = useId();
  const [v, setV] = useState<KpiFormValues>({
    metric: kpi?.metric ?? '',
    description: kpi?.description ?? '',
    baseline: kpi ? String(Number(kpi.baseline)) : '',
    target: kpi ? String(Number(kpi.target)) : '',
    unit: kpi?.unit ?? '',
    target_date: kpi?.target_date ?? '',
    current_value: kpi?.current_value ? String(Number(kpi.current_value)) : '',
  });
  const set = (key: keyof KpiFormValues) => (e: { target: { value: string } }) =>
    setV((current) => ({ ...current, [key]: e.target.value }));

  async function submit(event: FormEvent) {
    event.preventDefault();
    const body = {
      metric: v.metric,
      description: v.description || null,
      baseline: v.baseline,
      target: v.target,
      unit: v.unit,
      target_date: v.target_date || null,
      current_value: v.current_value || null,
    };
    try {
      await action.mutateAsync(() =>
        mode === 'add'
          ? onboardingApi.addKpi(clientId, body)
          : mode === 'current'
            ? onboardingApi.updateKpi(clientId, kpi!.id, { current_value: v.current_value || null })
            : onboardingApi.updateKpi(clientId, kpi!.id, body),
      );
      toast({ title: mode === 'add' ? 'KPI target added.' : 'KPI updated.' });
      onClose();
    } catch (error) {
      toast({ title: errorMessage(error), tone: 'error' });
    }
  }

  const title =
    mode === 'add'
      ? 'Add KPI target'
      : mode === 'current'
        ? `Update current value: ${kpi?.metric}`
        : `Edit ${kpi?.metric}`;
  return (
    <Dialog
      open
      onClose={onClose}
      title={title}
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button type="submit" form={formId} variant="primary" disabled={action.isPending}>
            Save
          </Button>
        </>
      }
    >
      <form id={formId} onSubmit={submit} className="grid gap-3 sm:grid-cols-2">
        {mode !== 'current' ? (
          <>
            <div className="sm:col-span-2">
              <TextField
                label="Metric *"
                required
                maxLength={120}
                placeholder="Organic Sessions"
                value={v.metric}
                onChange={set('metric')}
              />
            </div>
            <div className="sm:col-span-2">
              <TextField
                label="Description"
                maxLength={200}
                placeholder="Total organic sessions"
                value={v.description}
                onChange={set('description')}
              />
            </div>
            <TextField
              label="Baseline *"
              required
              inputMode="decimal"
              value={v.baseline}
              onChange={set('baseline')}
            />
            <TextField
              label="Target *"
              required
              inputMode="decimal"
              value={v.target}
              onChange={set('target')}
            />
            <TextField
              label="Unit *"
              required
              maxLength={60}
              placeholder="/ month"
              value={v.unit}
              onChange={set('unit')}
            />
            <TextField
              label="Target date"
              type="date"
              value={v.target_date}
              onChange={set('target_date')}
            />
          </>
        ) : null}
        <div className="sm:col-span-2">
          <TextField
            label="Current value"
            inputMode="decimal"
            hint="Leave empty until it's measured."
            value={v.current_value}
            onChange={set('current_value')}
          />
        </div>
        {mode === 'edit' && kpi?.confirmed_at ? (
          <div className="sm:col-span-2">
            <Alert tone="warn">
              Changing the baseline, target, unit or date needs the client's confirmation again.
            </Alert>
          </div>
        ) : null}
      </form>
    </Dialog>
  );
}

function ConfirmBanner({ data, clientId }: { data: OnboardingDetail; clientId: string }) {
  const action = useOnboardingAction(clientId);
  const { toast } = useToast();
  const ids = { who: useId(), via: useId() };
  const [who, setWho] = useState('');
  const [via, setVia] = useState<ContactChannel>('email');
  const summary = data.kpi_summary;
  const pending = data.kpis.filter((k) => !k.confirmed_at).length;

  if (summary.confirmed_at && !pending) {
    return (
      <Card
        className="flex flex-wrap items-center justify-between gap-4 bg-ok-soft/40 px-6 py-5"
        data-testid="kpis-confirmed"
      >
        <div className="flex items-center gap-4">
          <CircleCheck aria-hidden className="size-10 text-ok" />
          <div>
            <div className="font-semibold">KPIs Confirmed</div>
            <div className="text-[13px] text-muted">
              Client has reviewed and confirmed all KPI targets on{' '}
              {formatDate(summary.confirmed_at)}.
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3 text-sm">
          <span className="text-muted">Confirmed by:</span>
          <Avatar name={summary.confirmed_by ?? '?'} size="sm" />
          <div>
            <div className="font-medium">{summary.confirmed_by}</div>
            <div className="text-xs text-muted">
              via {CHANNELS.find((c) => c.value === summary.confirmed_via)?.label}
            </div>
          </div>
          <Badge tone="ok">✓ Confirmed</Badge>
        </div>
      </Card>
    );
  }
  if (!data.kpis.length) return null;
  if (!data.permissions.confirm_kpis) {
    return (
      <Alert tone="warn" title="Awaiting client confirmation">
        {pending} KPI target(s) still need the client's confirmation.
      </Alert>
    );
  }
  return (
    <Card className="flex flex-wrap items-end justify-between gap-4 bg-warn-soft/40 px-6 py-5">
      <div className="min-w-[220px]">
        <div className="font-semibold">Record client confirmation</div>
        <div className="text-[13px] text-muted">
          {pending} KPI target(s) need the client's confirmation before onboarding can be completed.
        </div>
      </div>
      <form
        className="flex flex-wrap items-end gap-3"
        onSubmit={async (event) => {
          event.preventDefault();
          try {
            await action.mutateAsync(() => onboardingApi.confirmKpis(clientId, who, via));
            toast({ title: 'Client confirmation recorded.' });
          } catch (error) {
            toast({ title: errorMessage(error), tone: 'error' });
          }
        }}
      >
        <TextField
          id={ids.who}
          label="Confirmed by (client)"
          required
          value={who}
          onChange={(e) => setWho(e.target.value)}
        />
        <SelectField
          id={ids.via}
          label="Communicated via"
          options={CHANNELS}
          value={via}
          onChange={(e) => setVia(e.target.value as ContactChannel)}
        />
        <Button type="submit" variant="primary" disabled={action.isPending}>
          Record confirmation
        </Button>
      </form>
    </Card>
  );
}

function NotesCard({ data, clientId }: { data: OnboardingDetail; clientId: string }) {
  const action = useOnboardingAction(clientId);
  const { toast } = useToast();
  const [editing, setEditing] = useState(false);
  const [notes, setNotes] = useState(data.kpi_summary.notes ?? '');
  const canEdit = data.permissions.owner;
  return (
    <Panel
      title="Notes"
      actions={
        canEdit && !editing ? (
          <Button size="sm" onClick={() => setEditing(true)}>
            <Pencil aria-hidden className="size-3.5" />
            Edit
          </Button>
        ) : null
      }
    >
      {editing ? (
        <div className="flex flex-col gap-2">
          <TextAreaField
            label="KPI notes"
            maxLength={2000}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />
          <div className="flex gap-2">
            <Button
              variant="primary"
              size="sm"
              onClick={async () => {
                try {
                  await action.mutateAsync(() => onboardingApi.kpiNotes(clientId, notes || null));
                  setEditing(false);
                } catch (error) {
                  toast({ title: errorMessage(error), tone: 'error' });
                }
              }}
            >
              Save
            </Button>
            <Button size="sm" onClick={() => setEditing(false)}>
              Cancel
            </Button>
          </div>
        </div>
      ) : data.kpi_summary.notes ? (
        <>
          <p className="text-sm whitespace-pre-wrap">{data.kpi_summary.notes}</p>
          {data.kpi_summary.notes_by ? (
            <div className="mt-4 flex items-center gap-3">
              <Avatar name={data.kpi_summary.notes_by.full_name} size="sm" />
              <div className="text-sm">
                <div className="font-medium">{data.kpi_summary.notes_by.full_name}</div>
                <div className="text-xs text-muted">
                  {data.kpi_summary.notes_at ? formatDate(data.kpi_summary.notes_at) : ''}
                </div>
              </div>
            </div>
          ) : null}
        </>
      ) : (
        <p className="text-sm text-muted">No notes yet.</p>
      )}
    </Panel>
  );
}

export function KpisTab({ clientId }: { clientId: string }) {
  const onboarding = useOnboarding(clientId);
  const action = useOnboardingAction(clientId);
  const { toast } = useToast();
  const [dialog, setDialog] = useState<{
    mode: 'add' | 'edit' | 'current';
    kpi: Kpi | null;
  } | null>(null);
  const data = onboarding.data;
  if (!data) return <EmptyState title="Loading KPI targets…" />;
  const s = data.kpi_summary;
  const pct = (n: number) => (s.total ? `${Math.round((n / s.total) * 100)}% of total` : '—');
  const manage = data.permissions.manage;
  const tracking = data.permissions.owner && data.client.status !== 'on_hold';

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold">KPI Targets</h2>
          <p className="mt-1 text-muted">
            Define measurable goals and track performance against targets.
          </p>
        </div>
        {manage ? (
          <Button variant="primary" onClick={() => setDialog({ mode: 'add', kpi: null })}>
            <Plus aria-hidden className="size-4" />
            Add KPI Target
          </Button>
        ) : null}
      </div>
      <div className="grid items-start gap-5 xl:grid-cols-[1fr_300px]">
        <div className="flex min-w-0 flex-col gap-5">
          <div className="grid gap-4 sm:grid-cols-2 2xl:grid-cols-4">
            <StatCard
              label="Total KPI Metrics"
              value={s.total}
              hint="All metrics"
              icon={UsersRound}
            />
            <StatCard
              label="On Track"
              value={s.on_track + s.achieved}
              hint={pct(s.on_track + s.achieved)}
              icon={TrendingUp}
              tone="ok"
            />
            <StatCard
              label="At Risk"
              value={s.at_risk}
              hint={pct(s.at_risk)}
              icon={AlarmClock}
              tone="warn"
            />
            <StatCard
              label="Behind"
              value={s.behind}
              hint={pct(s.behind)}
              icon={TrendingDown}
              tone="bad"
            />
          </div>
          <Card className="overflow-hidden">
            {data.kpis.length ? (
              <div className="overflow-x-auto">
                <table className="table" data-testid="kpi-table">
                  <thead>
                    <tr>
                      <th>KPI Metric</th>
                      <th>Baseline</th>
                      <th>Target</th>
                      <th>Target Date</th>
                      <th className="min-w-[180px]">Progress</th>
                      <th>Status</th>
                      <th className="text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.kpis.map((kpi) => (
                      <tr key={kpi.id}>
                        <td>
                          <div className="flex items-center gap-3">
                            <span className="grid size-9 place-items-center rounded-lg bg-accent-soft text-accent">
                              <Target aria-hidden className="size-4" />
                            </span>
                            <div>
                              <div className="font-medium">{kpi.metric}</div>
                              {kpi.description ? (
                                <div className="text-xs text-muted">{kpi.description}</div>
                              ) : null}
                            </div>
                          </div>
                        </td>
                        <td className="whitespace-nowrap">
                          {num(kpi.baseline)}
                          <div className="text-xs text-muted">{kpi.unit}</div>
                        </td>
                        <td className="whitespace-nowrap">
                          {num(kpi.target)}
                          <div className="text-xs text-muted">{kpi.unit}</div>
                        </td>
                        <td className="whitespace-nowrap">
                          {kpi.target_date ? formatDate(kpi.target_date) : '—'}
                          {kpi.target_date ? (
                            <div className="text-xs text-muted">
                              {months(kpi.confirmed_at ?? data.client.created_at, kpi.target_date)
                                ? `(${months(kpi.confirmed_at ?? data.client.created_at, kpi.target_date)})`
                                : ''}
                            </div>
                          ) : null}
                        </td>
                        <td>
                          <div className="text-xs text-muted">
                            {num(kpi.current_value)} / {num(kpi.target)}
                          </div>
                          {kpi.progress !== null ? (
                            <Progress value={kpi.progress} label={`${kpi.metric} progress`} />
                          ) : (
                            <span className="text-xs text-faint">Not measured yet</span>
                          )}
                        </td>
                        <td>
                          <Badge tone={KPI_STATUS[kpi.status].tone}>
                            {KPI_STATUS[kpi.status].label}
                          </Badge>
                          {!kpi.confirmed_at ? (
                            <div className="mt-1 text-[11px] text-warn">Awaiting client</div>
                          ) : null}
                        </td>
                        <td className="text-right">
                          <Menu
                            label={`Actions for ${kpi.metric}`}
                            items={[
                              {
                                label: 'Update current value',
                                hidden: !tracking,
                                onSelect: () => setDialog({ mode: 'current', kpi }),
                              },
                              {
                                label: 'Edit target',
                                hidden: !manage,
                                onSelect: () => setDialog({ mode: 'edit', kpi }),
                              },
                              {
                                label: 'Remove',
                                danger: true,
                                hidden: !manage || Boolean(kpi.confirmed_at),
                                onSelect: async () => {
                                  try {
                                    await action.mutateAsync(() =>
                                      onboardingApi.deleteKpi(clientId, kpi.id),
                                    );
                                    toast({ title: `${kpi.metric} removed.` });
                                  } catch (error) {
                                    toast({ title: errorMessage(error), tone: 'error' });
                                  }
                                },
                              },
                            ]}
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <EmptyState
                title="No KPI targets"
                description="Add at least one measurable target, then record the client's confirmation."
              />
            )}
            {manage ? (
              <button
                type="button"
                onClick={() => setDialog({ mode: 'add', kpi: null })}
                className="flex w-full cursor-pointer items-center justify-center gap-2 border-t border-line-soft py-4 text-sm font-medium text-accent hover:bg-accent-soft/40"
              >
                <Plus aria-hidden className="size-4" />
                Add New KPI Metric
              </button>
            ) : null}
          </Card>
        </div>
        <div className="flex flex-col gap-5">
          <Panel title="Overall Progress">
            <div className="flex items-center gap-5">
              <Ring value={s.overall ?? 0} size={120} label="Overall KPI progress">
                <div>
                  <div className="text-2xl font-bold">
                    {s.overall === null ? '—' : `${s.overall}%`}
                  </div>
                  <div className="text-xs text-muted">Overall</div>
                </div>
              </Ring>
              <ul className="flex flex-col gap-2 text-sm">
                <li className="flex items-center gap-2">
                  <span className="size-2.5 rounded-full bg-ok" />
                  On Track ({s.on_track + s.achieved})
                </li>
                <li className="flex items-center gap-2">
                  <span className="size-2.5 rounded-full bg-warn" />
                  At Risk ({s.at_risk})
                </li>
                <li className="flex items-center gap-2">
                  <span className="size-2.5 rounded-full bg-bad" />
                  Behind ({s.behind})
                </li>
              </ul>
            </div>
            <p className="mt-4 text-sm text-muted">
              {s.on_track + s.achieved} of {s.total} targets on track
            </p>
          </Panel>
          <NotesCard data={data} clientId={clientId} />
        </div>
      </div>
      <ConfirmBanner data={data} clientId={clientId} />
      {dialog ? (
        <KpiDialog
          clientId={clientId}
          kpi={dialog.kpi}
          mode={dialog.mode}
          onClose={() => setDialog(null)}
        />
      ) : null}
    </div>
  );
}
