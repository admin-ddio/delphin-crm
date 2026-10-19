/**
 * Client page → Onboarding tab: the 13-step workflow (layout, wording and
 * section numbering from the clickable demo). The server enforces every rule;
 * buttons only show for what the signed-in user may do.
 */
import { Check, Copy, X } from 'lucide-react';
import { useId, useState, type FormEvent, type ReactNode } from 'react';

import { Alert } from '@/components/ui/Alert';
import { Badge, type BadgeTone } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Panel } from '@/components/ui/Card';
import { KeyValue, Progress, StepList, type StepState } from '@/components/ui/Data';
import { EmptyState } from '@/components/ui/EmptyState';
import { useToast } from '@/components/ui/Toast';
import type { ClientDetail } from '@/features/clients/api';
import {
  onboardingApi,
  useOnboarding,
  useOnboardingAction,
  useTeamOptions,
  type AccessItem,
  type AccessStatus,
  type ContactChannel,
  type OnboardingDetail,
} from '@/features/onboarding/api';
import { ApiError } from '@/lib/api-client';
import { formatDate, formatDateTime } from '@/lib/format';

export const ONBOARDING_STATUS: Record<OnboardingDetail['status'], { label: string; tone: BadgeTone }> = {
  in_progress: { label: 'In progress', tone: 'accent' },
  blocked: { label: 'Blocked', tone: 'bad' },
  completed: { label: 'Completed', tone: 'ok' },
};

const ACCESS_TONE: Record<AccessStatus, BadgeTone> = {
  pending: 'neutral',
  requested: 'accent',
  received: 'accent',
  verified: 'ok',
  rejected: 'bad',
  not_required: 'neutral',
};

const CHANNELS: { value: ContactChannel; label: string }[] = [
  { value: 'email', label: 'Email' },
  { value: 'call', label: 'Call' },
  { value: 'meeting', label: 'Meeting' },
  { value: 'whatsapp', label: 'WhatsApp' },
];

const STEP_STATE: Record<string, StepState> = {
  todo: 'todo',
  progress: 'progress',
  done: 'done',
  blocked: 'blocked',
};

const number = (value: string | number) =>
  Number(value).toLocaleString('en-US', { maximumFractionDigits: 4 });

type Run = (work: () => Promise<OnboardingDetail>, success?: string) => Promise<boolean>;

function useRun(clientId: string): { run: Run; busy: boolean } {
  const action = useOnboardingAction(clientId);
  const { toast } = useToast();
  const run: Run = async (work, success) => {
    try {
      await action.mutateAsync(work);
      if (success) toast({ title: success });
      return true;
    } catch (error) {
      toast({
        title: error instanceof ApiError ? error.message : 'Something went wrong. Try again.',
        tone: 'error',
      });
      return false;
    }
  };
  return { run, busy: action.isPending };
}

// ================================================================ sections

function ContractSection({ data, run, busy }: { data: OnboardingDetail; run: Run; busy: boolean }) {
  const id = data.client_id;
  const can = data.permissions.manage;
  return (
    <Panel title="1 · Contract" description="Only authorised roles can mark a contract as signed.">
      <div className="flex flex-wrap items-center gap-2">
        {data.contract === 'signed' ? (
          <Badge tone="ok">Signed {data.contract_signed_at ? formatDate(data.contract_signed_at) : ''}</Badge>
        ) : data.contract === 'draft' ? (
          <Badge tone="warn">Recorded, unsigned</Badge>
        ) : (
          <Badge>No contract</Badge>
        )}
        {can && data.contract === 'none' ? (
          <Button size="sm" disabled={busy} onClick={() => run(() => onboardingApi.contract(id, 'record'), 'Contract recorded')}>
            Record contract
          </Button>
        ) : null}
        {can && data.contract === 'draft' ? (
          <Button size="sm" variant="primary" disabled={busy} onClick={() => run(() => onboardingApi.contract(id, 'sign'), 'Contract marked as signed')}>
            Mark signed
          </Button>
        ) : null}
      </div>
    </Panel>
  );
}

function QuestionnaireSection({ data, run, busy }: { data: OnboardingDetail; run: Run; busy: boolean }) {
  const id = data.client_id;
  const can = data.permissions.manage;
  const [link, setLink] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [recording, setRecording] = useState(false);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const formId = useId();

  async function send() {
    await run(async () => {
      const result = await onboardingApi.sendQuestionnaire(id);
      setLink(result.url);
      setCopied(false);
      return result.onboarding;
    }, 'Questionnaire link created (single-use, 30 days)');
  }

  async function record(event: FormEvent) {
    event.preventDefault();
    if (await run(() => onboardingApi.recordAnswers(id, answers), 'Answers recorded')) {
      setRecording(false);
    }
  }

  return (
    <Panel
      title="4–5 · Onboarding questionnaire"
      description="Business goals, products, markets, audiences, competitors and brand voice."
    >
      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-2">
          {data.questionnaire === 'submitted' ? (
            <Badge tone="ok">Submitted</Badge>
          ) : data.questionnaire === 'sent' ? (
            <Badge tone="accent">Sent · awaiting client</Badge>
          ) : (
            <Badge>Not sent</Badge>
          )}
          {can && data.questionnaire !== 'submitted' ? (
            <Button size="sm" disabled={busy} onClick={send}>
              {data.questionnaire === 'sent' ? 'Send a new link' : 'Send questionnaire link'}
            </Button>
          ) : null}
          {can && data.questionnaire === 'sent' && !recording ? (
            <Button size="sm" variant="primary" onClick={() => setRecording(true)}>
              Record client's answers
            </Button>
          ) : null}
        </div>

        {link ? (
          <Alert tone="info" title="Send this link to the client">
            <p className="mb-2 text-muted">
              It works once and expires in 30 days. It's only shown now; send a new link if it's lost.
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <code className="code break-all" data-testid="questionnaire-link">
                {link}
              </code>
              <Button
                size="sm"
                onClick={async () => {
                  await navigator.clipboard?.writeText(link);
                  setCopied(true);
                }}
              >
                {copied ? <Check aria-hidden className="size-3.5" /> : <Copy aria-hidden className="size-3.5" />}
                {copied ? 'Copied' : 'Copy'}
              </Button>
            </div>
          </Alert>
        ) : null}

        {recording ? (
          <form id={formId} className="flex flex-col gap-3" onSubmit={record}>
            {data.questions.map((q) => (
              <div key={q.key} className="label">
                <label htmlFor={`${formId}-${q.key}`}>{q.label}</label>
                <textarea
                  id={`${formId}-${q.key}`}
                  className="input min-h-[60px] resize-y"
                  value={answers[q.key] ?? ''}
                  onChange={(e) => setAnswers((a) => ({ ...a, [q.key]: e.target.value }))}
                />
              </div>
            ))}
            <div className="flex gap-2">
              <Button type="submit" size="sm" variant="primary" disabled={busy}>
                Save answers
              </Button>
              <Button size="sm" onClick={() => setRecording(false)}>
                Cancel
              </Button>
            </div>
          </form>
        ) : null}

        {data.questionnaire === 'submitted' ? (
          <KeyValue items={data.questions.map((q) => [q.label, q.answer] as [string, ReactNode])} />
        ) : null}
      </div>
    </Panel>
  );
}

function AccessRow({ item, data, run, busy }: { item: AccessItem; data: OnboardingDetail; run: Run; busy: boolean }) {
  const id = data.client_id;
  const { manage, verify_access: verify } = data.permissions;
  const set = (status: AccessStatus, message: string) =>
    run(() => onboardingApi.access(id, item.key, status), message);
  return (
    <tr>
      <td>{item.label}</td>
      <td>
        <Badge tone={ACCESS_TONE[item.status]}>{item.status.replace('_', ' ')}</Badge>
      </td>
      <td>
        {item.verified_by ? (
          <>
            {item.verified_by.full_name} <span className="code">manual</span>
          </>
        ) : (
          '—'
        )}
      </td>
      <td>
        <div className="flex flex-wrap justify-end gap-1.5">
          {manage && ['pending', 'requested', 'rejected'].includes(item.status) ? (
            <Button size="sm" disabled={busy} onClick={() => set('received', `${item.label}: received`)}>
              Mark received
            </Button>
          ) : null}
          {verify && item.status === 'received' ? (
            <>
              <Button size="sm" variant="primary" disabled={busy} onClick={() => set('verified', 'Access verified')}>
                Verify
              </Button>
              <Button size="sm" disabled={busy} onClick={() => set('rejected', 'Access rejected — onboarding is blocked until it’s fixed')}>
                Reject
              </Button>
            </>
          ) : null}
          {manage && ['pending', 'requested', 'rejected'].includes(item.status) ? (
            <Button size="sm" variant="ghost" disabled={busy} onClick={() => set('not_required', `${item.label}: not required`)}>
              Not required
            </Button>
          ) : null}
          {manage && item.status === 'not_required' ? (
            <Button size="sm" variant="ghost" disabled={busy} onClick={() => set('pending', `${item.label}: required again`)}>
              Required again
            </Button>
          ) : null}
        </div>
      </td>
    </tr>
  );
}

function AccessSection({ data, run, busy }: { data: OnboardingDetail; run: Run; busy: boolean }) {
  const waiting = data.access.some((a) => a.status === 'pending' || a.status === 'requested');
  return (
    <Panel
      title="6–7 · Platform access"
      description="Never store passwords here. Verification means a named person confirmed it manually; it's not a live API connection."
      flush
      actions={
        data.permissions.manage && waiting ? (
          <Button
            size="sm"
            disabled={busy}
            onClick={() =>
              run(() => onboardingApi.receiveAll(data.client_id), 'All access marked received — now verify each item')
            }
          >
            Mark all received
          </Button>
        ) : null
      }
    >
      <div className="overflow-x-auto">
        <table className="table">
          <thead>
            <tr>
              <th>Platform</th>
              <th>Status</th>
              <th>Verified by</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {data.access.map((item) => (
              <AccessRow key={item.key} item={item} data={data} run={run} busy={busy} />
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function KpiSection({ data, client, run, busy }: { data: OnboardingDetail; client: ClientDetail; run: Run; busy: boolean }) {
  const id = data.client_id;
  const formId = useId();
  const [kpi, setKpi] = useState({ metric: '', baseline: '', target: '', unit: '' });
  const [confirmedBy, setConfirmedBy] = useState(client.contact_name ?? '');
  const [via, setVia] = useState<ContactChannel>('email');
  const unconfirmed = data.kpis.some((k) => !k.confirmed_at);

  async function add(event: FormEvent) {
    event.preventDefault();
    const ok = await run(
      () => onboardingApi.addKpi(id, { ...kpi, baseline: kpi.baseline, target: kpi.target }),
      'KPI target added',
    );
    if (ok) setKpi({ metric: '', baseline: '', target: '', unit: '' });
  }

  return (
    <Panel
      title="8 · KPI targets"
      description="Targets need the client's confirmation before onboarding can be completed."
      flush
    >
      {data.kpis.length ? (
        <div className="overflow-x-auto">
          <table className="table">
            <thead>
              <tr>
                <th>Metric</th>
                <th>Baseline → target</th>
                <th>Client confirmation</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {data.kpis.map((k) => (
                <tr key={k.id}>
                  <td>{k.metric}</td>
                  <td className="font-mono tabular-nums">
                    {number(k.baseline)} → <b>{number(k.target)}</b> {k.unit}
                  </td>
                  <td>
                    {k.confirmed_at ? (
                      <Badge tone="ok">Confirmed by {k.confirmed_by_name}</Badge>
                    ) : (
                      <Badge tone="warn">Awaiting client</Badge>
                    )}
                  </td>
                  <td className="text-right">
                    {data.permissions.manage && !k.confirmed_at ? (
                      <Button
                        size="sm"
                        variant="ghost"
                        aria-label={`Remove ${k.metric}`}
                        disabled={busy}
                        onClick={() => run(() => onboardingApi.deleteKpi(id, k.id), 'KPI target removed')}
                      >
                        <X aria-hidden className="size-3.5" />
                      </Button>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <EmptyState title="No KPI targets" description="Add at least one measurable target." />
      )}

      {data.permissions.manage ? (
        <form className="flex flex-col gap-3 border-t border-line-soft p-3.5" onSubmit={add}>
          <div className="grid grid-cols-[repeat(auto-fit,minmax(150px,1fr))] gap-3">
            {(
              [
                ['metric', 'Metric', 'Organic sessions', 'text'],
                ['baseline', 'Baseline', '', 'number'],
                ['target', 'Target', '', 'number'],
                ['unit', 'Unit', 'sessions / month', 'text'],
              ] as const
            ).map(([field, label, placeholder, type]) => (
              <div key={field} className="label">
                <label htmlFor={`${formId}-${field}`}>{label}</label>
                <input
                  id={`${formId}-${field}`}
                  className="input"
                  type={type}
                  step="any"
                  required
                  placeholder={placeholder}
                  value={kpi[field]}
                  onChange={(e) => setKpi((v) => ({ ...v, [field]: e.target.value }))}
                />
              </div>
            ))}
          </div>
          <div>
            <Button type="submit" size="sm" disabled={busy}>
              Add KPI target
            </Button>
          </div>
        </form>
      ) : null}

      {data.permissions.confirm_kpis && unconfirmed ? (
        <form
          className="flex flex-wrap items-end gap-3 border-t border-line-soft p-3.5"
          onSubmit={(e) => {
            e.preventDefault();
            void run(() => onboardingApi.confirmKpis(id, confirmedBy, via), 'Client confirmation recorded');
          }}
        >
          <div className="label min-w-[200px] flex-1">
            <label htmlFor={`${formId}-who`}>Confirmed by (at the client)</label>
            <input
              id={`${formId}-who`}
              className="input"
              required
              value={confirmedBy}
              onChange={(e) => setConfirmedBy(e.target.value)}
            />
          </div>
          <div className="label">
            <label htmlFor={`${formId}-via`}>Communicated via</label>
            <select id={`${formId}-via`} className="input" value={via} onChange={(e) => setVia(e.target.value as ContactChannel)}>
              {CHANNELS.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </select>
          </div>
          <Button type="submit" size="sm" variant="primary" disabled={busy}>
            Record client confirmation
          </Button>
        </form>
      ) : null}
    </Panel>
  );
}

function KickoffRow({
  kind,
  label,
  data,
  run,
  busy,
}: {
  kind: 'client' | 'internal';
  label: string;
  data: OnboardingDetail;
  run: Run;
  busy: boolean;
}) {
  const kickoff = kind === 'client' ? data.kickoff_client : data.kickoff_internal;
  const [open, setOpen] = useState(false);
  const [when, setWhen] = useState('');
  const [notes, setNotes] = useState('');
  const fieldId = useId();
  const can = data.permissions.manage;
  const completeLabel = kind === 'client' ? 'Complete with notes' : 'Complete with responsibilities';

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        <span className="min-w-[140px]">{label}</span>
        {kickoff.status === 'done' ? (
          <Badge tone="ok">Completed</Badge>
        ) : kickoff.status === 'scheduled' ? (
          <Badge tone="accent">Scheduled{kickoff.at ? ` · ${formatDateTime(kickoff.at)}` : ''}</Badge>
        ) : (
          <Badge>Not scheduled</Badge>
        )}
        {can && kickoff.status !== 'done' && !open ? (
          <Button size="sm" variant={kickoff.status === 'scheduled' ? 'primary' : 'secondary'} onClick={() => setOpen(true)}>
            {kickoff.status === 'none' ? 'Schedule' : completeLabel}
          </Button>
        ) : null}
      </div>
      {kickoff.notes ? <p className="text-[13px] text-muted">Notes: {kickoff.notes}</p> : null}
      {open ? (
        <form
          className="flex flex-wrap items-end gap-2"
          onSubmit={async (e) => {
            e.preventDefault();
            const scheduling = kickoff.status === 'none';
            const ok = await run(
              () =>
                onboardingApi.kickoff(data.client_id, kind, {
                  action: scheduling ? 'schedule' : 'complete',
                  at: when ? new Date(when).toISOString() : null,
                  notes: scheduling ? null : notes || null,
                }),
              scheduling ? 'Meeting scheduled' : 'Meeting completed',
            );
            if (ok) setOpen(false);
          }}
        >
          {kickoff.status === 'none' ? (
            <div className="label">
              <label htmlFor={`${fieldId}-when`}>Date & time (optional)</label>
              <input id={`${fieldId}-when`} className="input" type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} />
            </div>
          ) : (
            <div className="label min-w-[260px] flex-1">
              <label htmlFor={`${fieldId}-notes`}>{kind === 'client' ? 'Notes' : 'Responsibilities'}</label>
              <textarea id={`${fieldId}-notes`} className="input min-h-[56px]" value={notes} onChange={(e) => setNotes(e.target.value)} />
            </div>
          )}
          <Button type="submit" size="sm" variant="primary" disabled={busy}>
            Save
          </Button>
          <Button size="sm" onClick={() => setOpen(false)}>
            Cancel
          </Button>
        </form>
      ) : null}
    </div>
  );
}

function TeamRow({ data, run, busy }: { data: OnboardingDetail; run: Run; busy: boolean }) {
  const can = data.permissions.manage;
  const options = useTeamOptions(data.client_id, can);
  const [choice, setChoice] = useState('');
  const selectId = useId();
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="min-w-[140px]">Internal team</span>
      {data.team.length ? (
        data.team.map((member) => (
          <Badge key={member.id} tone="accent" className="gap-1">
            {member.full_name}
            {can ? (
              <button
                type="button"
                aria-label={`Remove ${member.full_name}`}
                className="opacity-70 hover:opacity-100"
                onClick={() => run(() => onboardingApi.removeTeamMember(data.client_id, member.id), `${member.full_name} removed`)}
              >
                <X aria-hidden className="size-3" />
              </button>
            ) : null}
          </Badge>
        ))
      ) : (
        <span className="text-muted">No one assigned</span>
      )}
      {can ? (
        <>
          <label className="sr-only" htmlFor={selectId}>
            Team member
          </label>
          <select id={selectId} className="input py-1" value={choice} onChange={(e) => setChoice(e.target.value)}>
            <option value="">Choose a person…</option>
            {options.data?.map((u) => (
              <option key={u.id} value={u.id}>
                {u.full_name}
              </option>
            ))}
          </select>
          <Button
            size="sm"
            disabled={busy || !choice}
            onClick={async () => {
              if (await run(() => onboardingApi.addTeamMember(data.client_id, choice), 'Team member assigned')) setChoice('');
            }}
          >
            Assign
          </Button>
          {options.data?.length === 0 ? (
            <span className="text-xs text-muted">No employees, team leads or PMs available yet.</span>
          ) : null}
        </>
      ) : null}
    </div>
  );
}

function CompletionSection({ data, run, busy }: { data: OnboardingDetail; run: Run; busy: boolean }) {
  const ready = data.steps.slice(0, 10).every((s) => s.state === 'done');
  if (data.completed_at) {
    return (
      <Panel title="11–12 · Review & completion">
        <Alert tone="ok" title={`Onboarding completed ${formatDate(data.completed_at)}`}>
          The client is Active. Project creation arrives with the Projects module.
        </Alert>
      </Panel>
    );
  }
  return (
    <Panel title="11–12 · Review & completion">
      <div className="flex flex-col gap-3">
        <p className="text-muted">
          The review only passes when steps 1–10 are complete. Completion is checked again on the
          server: all access verified, all KPIs client-confirmed.
        </p>
        {data.permissions.manage ? (
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              disabled={busy || Boolean(data.reviewed_at)}
              onClick={() => run(() => onboardingApi.review(data.client_id), 'Onboarding review passed')}
            >
              {data.reviewed_at && ready ? 'Review passed ✓' : 'Pass onboarding review'}
            </Button>
            <Button
              size="sm"
              variant="primary"
              disabled={busy}
              onClick={() => run(() => onboardingApi.complete(data.client_id), 'Onboarding completed. The client is now Active.')}
            >
              Complete onboarding
            </Button>
          </div>
        ) : null}
      </div>
    </Panel>
  );
}

// ================================================================ tab

export function OnboardingTab({ client }: { client: ClientDetail }) {
  const onboarding = useOnboarding(client.id);
  const { run, busy } = useRun(client.id);

  if (onboarding.isPending) return <EmptyState title="Loading onboarding…" />;
  if (onboarding.isError || !onboarding.data) {
    return <Alert tone="bad">Couldn't load onboarding. Reload the page to try again.</Alert>;
  }
  const data = onboarding.data;
  const status = ONBOARDING_STATUS[data.status];
  const readOnly =
    !data.permissions.manage && !data.permissions.verify_access && !data.permissions.confirm_kpis;

  return (
    <div className="grid items-start gap-4 min-[861px]:grid-cols-[250px_minmax(0,1fr)]" data-testid="onboarding">
      <Panel>
        <h3 className="mb-2 text-xs font-semibold tracking-[.06em] text-muted uppercase">Overall progress</h3>
        <Progress value={data.progress} label="Onboarding progress" />
        <p className="mt-1.5 mb-3 text-xs text-muted">
          Status: <Badge tone={status.tone}>{status.label}</Badge>
        </p>
        <StepList
          steps={data.steps.map((s) => ({
            label: s.label,
            state: STEP_STATE[s.state] ?? 'todo',
            detail: s.detail || undefined,
          }))}
        />
      </Panel>

      <div className="flex flex-col gap-4">
        {readOnly && !data.completed_at ? (
          <Alert tone="info" title="Read-only">
            You can follow this onboarding but not change it. The client's Account Manager runs the
            workflow.
          </Alert>
        ) : null}
        <ContractSection data={data} run={run} busy={busy} />
        <QuestionnaireSection data={data} run={run} busy={busy} />
        <AccessSection data={data} run={run} busy={busy} />
        <KpiSection data={data} client={client} run={run} busy={busy} />
        <Panel title="9–10 · Kickoffs & team">
          <div className="flex flex-col gap-3">
            <KickoffRow kind="client" label="Client kickoff" data={data} run={run} busy={busy} />
            <TeamRow data={data} run={run} busy={busy} />
            <KickoffRow kind="internal" label="Internal kickoff" data={data} run={run} busy={busy} />
          </div>
        </Panel>
        <CompletionSection data={data} run={run} busy={busy} />
      </div>
    </div>
  );
}
