/**
 * The review part of a task (task drawer and pages), from the clickable demo:
 * "Submit for review" form, the open request with its decision form, and the
 * versions & feedback history. Buttons follow TaskDetail.permissions.
 */
import { useId, useState, type FormEvent } from 'react';

import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { useToast } from '@/components/ui/Toast';
import { CHANNELS, useDecide, useSubmitForReview, type Channel } from '@/features/approvals/api';
import type { TaskDetail } from '@/features/tasks/api';
import { ApiError } from '@/lib/api-client';
import { formatDateTime } from '@/lib/format';

type OpenApproval = NonNullable<TaskDetail['open_approval']>;

function errorMessage(error: unknown) {
  return error instanceof ApiError ? error.message : 'Something went wrong. Try again.';
}

export function SubmitForm({ task, onDone }: { task: TaskDetail; onDone(): void }) {
  const submit = useSubmitForReview();
  const { toast } = useToast();
  const noteId = useId();
  const linkId = useId();
  const [note, setNote] = useState('');
  const [link, setLink] = useState('');
  const next = task.versions.length + 1;

  async function send(event: FormEvent) {
    event.preventDefault();
    try {
      const updated = await submit.mutateAsync({ task_id: task.id, note, link: link || null });
      const stage = updated.open_approval?.stage === 'client' ? 'client approval' : 'review';
      toast({ title: `v${next} submitted for ${stage}.` });
      onDone();
    } catch (error) {
      toast({ title: errorMessage(error), tone: 'error' });
    }
  }

  return (
    <form className="flex flex-col gap-3" onSubmit={send} data-testid="submit-form">
      <div className="label">
        <label htmlFor={noteId}>What changed / notes for the reviewer</label>
        <textarea
          id={noteId}
          className="input min-h-20"
          required
          maxLength={4000}
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
      </div>
      <div className="label">
        <label htmlFor={linkId}>Link to the work</label>
        <input
          id={linkId}
          type="url"
          className="input"
          placeholder="https://docs.example.com/…"
          maxLength={500}
          value={link}
          onChange={(e) => setLink(e.target.value)}
        />
      </div>
      <div className="flex gap-2">
        <Button type="submit" variant="primary" disabled={submit.isPending}>
          Submit v{next}
        </Button>
        <Button type="button" onClick={onDone}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

function DecisionForm({ request, task }: { request: OpenApproval; task: TaskDetail }) {
  const decide = useDecide(request.id);
  const { toast } = useToast();
  const ids = { who: useId(), via: useId(), note: useId() };
  const client = request.stage === 'client';
  const [who, setWho] = useState(task.client_contact ?? '');
  const [via, setVia] = useState<Channel>('email');
  const [note, setNote] = useState('');

  async function send(decision: 'approved' | 'changes') {
    try {
      const updated = await decide.mutateAsync({
        decision,
        note: note || null,
        client_decider: client ? who : null,
        client_channel: client ? via : null,
      });
      toast({
        title:
          decision === 'changes'
            ? 'Changes requested — sent back to the assignee.'
            : updated.status === 'completed'
              ? 'Approved — task completed.'
              : 'Approved — client approval requested.',
      });
    } catch (error) {
      toast({ title: errorMessage(error), tone: 'error' });
    }
  }

  return (
    <form
      className="flex flex-col gap-3"
      data-testid="decision-form"
      onSubmit={(event) => {
        event.preventDefault();
        void send('approved');
      }}
    >
      {client ? (
        <div className="grid grid-cols-2 gap-3">
          <div className="label">
            <label htmlFor={ids.who}>Client decision-maker</label>
            <input
              id={ids.who}
              className="input"
              required
              maxLength={200}
              value={who}
              onChange={(e) => setWho(e.target.value)}
            />
          </div>
          <div className="label">
            <label htmlFor={ids.via}>Communicated via</label>
            <select
              id={ids.via}
              className="input"
              value={via}
              onChange={(e) => setVia(e.target.value as Channel)}
            >
              {CHANNELS.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </select>
          </div>
        </div>
      ) : null}
      <div className="label">
        <label htmlFor={ids.note}>
          {client ? 'Client feedback' : 'Feedback'} (required to request changes)
        </label>
        <textarea
          id={ids.note}
          className="input min-h-16"
          maxLength={4000}
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
      </div>
      <div className="flex gap-2">
        <Button type="submit" variant="primary" disabled={decide.isPending}>
          Approve
        </Button>
        <Button type="button" disabled={decide.isPending} onClick={() => void send('changes')}>
          Request changes
        </Button>
      </div>
    </form>
  );
}

export function ReviewPanel({ task }: { task: TaskDetail }) {
  const [submitting, setSubmitting] = useState(false);
  const request = task.open_approval;
  const { permissions } = task;
  return (
    <>
      {permissions.submit && !submitting ? (
        <div>
          <Button variant="primary" onClick={() => setSubmitting(true)}>
            Submit for review
          </Button>
        </div>
      ) : null}
      {permissions.submit && submitting ? (
        <SubmitForm task={task} onDone={() => setSubmitting(false)} />
      ) : null}
      {request ? (
        <>
          <Alert
            tone="info"
            title={`Awaiting ${request.stage === 'internal' ? 'internal review' : 'client approval'} · v${request.version}`}
          >
            {request.stage === 'internal'
              ? `Reviewer: ${request.approver?.full_name ?? '—'}`
              : `The Account Manager (${request.approver?.full_name ?? '—'}) records the client's decision.`}
          </Alert>
          {permissions.decide ? (
            <DecisionForm key={request.id} request={request} task={task} />
          ) : permissions.decide_blocked ? (
            <p className="text-muted">{permissions.decide_blocked}</p>
          ) : null}
        </>
      ) : null}
      <div>
        <h3 className="mb-1 text-sm font-semibold">Versions &amp; feedback</h3>
        {task.versions.length ? (
          <div className="flex flex-col gap-2" data-testid="versions">
            {[...task.versions].reverse().map((version) => (
              <div key={version.number} className="rounded-md border border-line p-2.5">
                <div>
                  <b>Version {version.number}</b>{' '}
                  <span className="code">
                    {version.submitted_by?.full_name ?? '—'} ·{' '}
                    {formatDateTime(version.submitted_at)}
                  </span>
                </div>
                <div className="mt-1 whitespace-pre-wrap">{version.note}</div>
                {version.link ? (
                  <a
                    className="link code break-all"
                    href={version.link}
                    target="_blank"
                    rel="noreferrer noopener"
                  >
                    {version.link}
                  </a>
                ) : null}
                {version.feedback.map((f, i) => (
                  <div key={i} className="mt-2 border-l-2 border-line pl-2 text-[13px]">
                    <b>{f.result === 'approved' ? 'Approved' : 'Changes requested'}</b> by {f.by} —{' '}
                    {f.note || 'No comment'}
                  </div>
                ))}
              </div>
            ))}
          </div>
        ) : (
          <p className="text-muted">Nothing submitted yet.</p>
        )}
      </div>
    </>
  );
}
