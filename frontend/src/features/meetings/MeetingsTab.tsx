/**
 * Screen 7 – Meetings / Kickoff Call (product mockup): totals, meetings list (type,
 * date & time, attendees, status), a detail panel with notes and next actions, and
 * a drawer to schedule / edit, complete with notes, cancel and manage action items.
 * Completing a Kickoff meeting completes onboarding step 9; an Internal one, step 10.
 */
import {
  CalendarCheck,
  CalendarClock,
  CalendarDays,
  CalendarX,
  CircleCheck,
  Circle,
  Clock,
  Plus,
  Trash2,
  Video,
  ArrowRight,
} from 'lucide-react';
import { useEffect, useId, useMemo, useState, type FormEvent } from 'react';
import { useSearchParams } from 'react-router';

import { Avatar } from '@/components/ui/Avatar';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, Panel, StatCard } from '@/components/ui/Card';
import { Dialog, Drawer } from '@/components/ui/Dialog';
import { EmptyState } from '@/components/ui/EmptyState';
import { TextField } from '@/components/ui/Field';
import { SelectField, TextAreaField } from '@/components/ui/Fields';
import { Menu } from '@/components/ui/Menu';
import { useToast } from '@/components/ui/Toast';
import type { ClientDetail } from '@/features/clients/api';
import {
  MEETING_STATUS,
  MEETING_TYPES,
  meetingsApi,
  PLATFORMS,
  useClientMeetings,
  useMeetingAction,
  type Meeting,
  type MeetingType,
  type Platform,
} from '@/features/meetings/api';
import { useAssigneeOptions } from '@/features/tasks/api';
import { ApiError } from '@/lib/api-client';
import { formatDate, formatTime, localDateInput } from '@/lib/format';
import { cn } from '@/lib/utils';

function errorMessage(error: unknown) {
  return error instanceof ApiError ? error.message : 'Something went wrong. Try again.';
}

function typeOf(type: MeetingType) {
  return MEETING_TYPES.find((t) => t.value === type) ?? MEETING_TYPES[5]!;
}

function Attendees({ meeting, max = 3 }: { meeting: Meeting; max?: number }) {
  const shown = meeting.attendees.slice(0, max);
  const more = meeting.attendees.length - shown.length;
  return (
    <span
      className="flex items-center"
      aria-label={meeting.attendees.map((a) => a.name).join(', ')}
    >
      {shown.map((a) => (
        <Avatar
          key={a.id}
          name={a.name}
          size="xs"
          className="-ml-1.5 ring-2 ring-surface first:ml-0"
        />
      ))}
      {more > 0 ? (
        <span className="-ml-1.5 grid size-7 place-items-center rounded-full bg-sunk text-[11px] font-semibold ring-2 ring-surface">
          +{more}
        </span>
      ) : null}
      {!meeting.attendees.length ? <span className="text-muted">—</span> : null}
    </span>
  );
}

interface FormState {
  title: string;
  description: string;
  type: MeetingType;
  date: string;
  start: string;
  end: string;
  platform: Platform | '';
  location: string;
  agenda: string;
  attendeeIds: string[];
  guests: { name: string; email: string }[];
}

function toForm(meeting: Meeting | null, type: MeetingType = 'kickoff'): FormState {
  if (!meeting) {
    return {
      title: type === 'kickoff' ? 'Kickoff Call' : '',
      description: '',
      type,
      date: localDateInput(),
      start: '10:30',
      end: '11:30',
      platform: 'google_meet',
      location: '',
      agenda: '',
      attendeeIds: [],
      guests: [],
    };
  }
  const start = new Date(meeting.starts_at);
  const end = new Date(meeting.ends_at);
  const hhmm = (d: Date) => d.toTimeString().slice(0, 5);
  return {
    title: meeting.title,
    description: meeting.description ?? '',
    type: meeting.type,
    date: localDateInput(start),
    start: hhmm(start),
    end: hhmm(end),
    platform: meeting.platform ?? '',
    location: meeting.location ?? '',
    agenda: meeting.agenda ?? '',
    attendeeIds: meeting.attendees.filter((a) => a.user).map((a) => a.user!.id),
    guests: meeting.attendees
      .filter((a) => a.external)
      .map((a) => ({ name: a.name, email: a.email ?? '' })),
  };
}

function ScheduleDrawer({
  client,
  meeting,
  open,
  onClose,
  onSaved,
}: {
  client: ClientDetail;
  meeting: Meeting | null;
  open: boolean;
  onClose(): void;
  onSaved(id: string): void;
}) {
  const action = useMeetingAction(client.id);
  const people = useAssigneeOptions(open);
  const { toast } = useToast();
  const formId = useId();
  const [f, setF] = useState<FormState>(() => toForm(meeting));
  const meetingId = meeting?.id;
  useEffect(() => {
    if (open) setF(toForm(meeting));
    // Reset only when opened or switched to another meeting, not on every refetch.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, meetingId]);
  const set = <K extends keyof FormState>(key: K, value: FormState[K]) =>
    setF((c) => ({ ...c, [key]: value }));

  async function submit(event: FormEvent) {
    event.preventDefault();
    const startsAt = new Date(`${f.date}T${f.start}`);
    const endsAt = new Date(`${f.date}T${f.end}`);
    const body = {
      title: f.title,
      description: f.description || null,
      type: f.type,
      starts_at: startsAt.toISOString(),
      ends_at: endsAt.toISOString(),
      platform: f.platform || null,
      location: f.location || null,
      agenda: f.agenda || null,
      attendee_ids: f.attendeeIds,
      guests: f.guests
        .filter((g) => g.name.trim())
        .map((g) => ({ name: g.name, email: g.email || null })),
    };
    try {
      let saved: Meeting | undefined;
      await action.mutateAsync(async () => {
        saved = meeting
          ? await meetingsApi.update(meeting.id, body)
          : await meetingsApi.schedule({ client_id: client.id, ...body });
        return saved;
      });
      toast({ title: meeting ? 'Meeting updated.' : 'Meeting scheduled.' });
      if (saved) onSaved(saved.id);
      onClose();
    } catch (error) {
      toast({ title: errorMessage(error), tone: 'error' });
    }
  }

  return (
    <Drawer
      open={open}
      onClose={onClose}
      title={meeting ? 'Edit meeting' : 'Schedule meeting'}
      eyebrow={client.name}
      footer={
        <Button type="submit" form={formId} variant="primary" disabled={action.isPending}>
          {meeting ? 'Save meeting' : 'Schedule meeting'}
        </Button>
      }
    >
      <form id={formId} onSubmit={submit} className="flex flex-col gap-3">
        <TextField
          label="Title *"
          required
          maxLength={200}
          value={f.title}
          onChange={(e) => set('title', e.target.value)}
        />
        <TextField
          label="Description"
          maxLength={300}
          value={f.description}
          onChange={(e) => set('description', e.target.value)}
        />
        <div className="grid gap-3 sm:grid-cols-2">
          <SelectField
            label="Type"
            options={MEETING_TYPES}
            value={f.type}
            onChange={(e) => set('type', e.target.value as MeetingType)}
          />
          <SelectField
            label="Platform"
            placeholder="Choose…"
            options={PLATFORMS}
            value={f.platform}
            onChange={(e) => set('platform', e.target.value as Platform | '')}
          />
          <TextField
            label="Date *"
            type="date"
            required
            value={f.date}
            onChange={(e) => set('date', e.target.value)}
          />
          <div className="grid grid-cols-2 gap-2">
            <TextField
              label="Start *"
              type="time"
              required
              value={f.start}
              onChange={(e) => set('start', e.target.value)}
            />
            <TextField
              label="End *"
              type="time"
              required
              value={f.end}
              onChange={(e) => set('end', e.target.value)}
            />
          </div>
        </div>
        <TextField
          label="Link or location"
          maxLength={500}
          placeholder="https://meet.google.com/…"
          value={f.location}
          onChange={(e) => set('location', e.target.value)}
        />
        <TextAreaField
          label="Agenda"
          maxLength={4000}
          value={f.agenda}
          onChange={(e) => set('agenda', e.target.value)}
        />
        <fieldset className="flex flex-col gap-2">
          <legend className="mb-1 text-[13px] font-medium">Team attendees</legend>
          <div className="flex max-h-40 flex-wrap gap-2 overflow-y-auto">
            {(people.data ?? []).map((p) => {
              const on = f.attendeeIds.includes(p.id);
              return (
                <label
                  key={p.id}
                  className={cn(
                    'flex cursor-pointer items-center gap-2 rounded-full border px-3 py-1.5 text-[13px]',
                    on ? 'border-accent bg-accent-soft text-accent' : 'border-line',
                  )}
                >
                  <input
                    type="checkbox"
                    className="sr-only"
                    checked={on}
                    onChange={() =>
                      set(
                        'attendeeIds',
                        on ? f.attendeeIds.filter((i) => i !== p.id) : [...f.attendeeIds, p.id],
                      )
                    }
                  />
                  {p.full_name}
                </label>
              );
            })}
          </div>
        </fieldset>
        <fieldset className="flex flex-col gap-2">
          <legend className="mb-1 text-[13px] font-medium">Client guests</legend>
          {f.guests.map((g, i) => (
            <div key={i} className="grid grid-cols-[1fr_1fr_auto] items-end gap-2">
              <TextField
                label={`Guest ${i + 1} name`}
                value={g.name}
                onChange={(e) =>
                  set(
                    'guests',
                    f.guests.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)),
                  )
                }
              />
              <TextField
                label={`Guest ${i + 1} e-mail`}
                type="email"
                value={g.email}
                onChange={(e) =>
                  set(
                    'guests',
                    f.guests.map((x, j) => (j === i ? { ...x, email: e.target.value } : x)),
                  )
                }
              />
              <Button
                aria-label={`Remove guest ${i + 1}`}
                onClick={() =>
                  set(
                    'guests',
                    f.guests.filter((_, j) => j !== i),
                  )
                }
              >
                <Trash2 aria-hidden className="size-4" />
              </Button>
            </div>
          ))}
          <div>
            <Button
              size="sm"
              onClick={() =>
                set('guests', [
                  ...f.guests,
                  {
                    name: f.guests.length ? '' : (client.contact_name ?? ''),
                    email: f.guests.length ? '' : (client.contact_email ?? ''),
                  },
                ])
              }
            >
              <Plus aria-hidden className="size-3.5" />
              Add guest
            </Button>
          </div>
        </fieldset>
      </form>
    </Drawer>
  );
}

function CompleteDialog({
  meeting,
  clientId,
  onClose,
}: {
  meeting: Meeting;
  clientId: string;
  onClose(): void;
}) {
  const action = useMeetingAction(clientId);
  const { toast } = useToast();
  const [notes, setNotes] = useState(meeting.notes ?? '');
  return (
    <Dialog
      open
      onClose={onClose}
      title={`Complete: ${meeting.title}`}
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button
            variant="primary"
            disabled={!notes.trim() || action.isPending}
            onClick={async () => {
              try {
                await action.mutateAsync(() => meetingsApi.complete(meeting.id, notes));
                toast({ title: 'Meeting completed.' });
                onClose();
              } catch (error) {
                toast({ title: errorMessage(error), tone: 'error' });
              }
            }}
          >
            Mark completed
          </Button>
        </>
      }
    >
      <TextAreaField
        label="Meeting notes *"
        hint="One point per line: decisions, goals, next steps."
        maxLength={8000}
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
      />
    </Dialog>
  );
}

function DetailPanel({
  meeting,
  clientId,
  onEdit,
}: {
  meeting: Meeting;
  clientId: string;
  onEdit(): void;
}) {
  const action = useMeetingAction(clientId);
  const people = useAssigneeOptions(meeting.can_manage);
  const { toast } = useToast();
  const [completing, setCompleting] = useState(false);
  const [item, setItem] = useState('');
  const [owner, setOwner] = useState('');
  const [due, setDue] = useState('');
  const status = MEETING_STATUS[meeting.display_status];
  const run = async (call: () => Promise<Meeting>, done?: string) => {
    try {
      await action.mutateAsync(call);
      if (done) toast({ title: done });
    } catch (error) {
      toast({ title: errorMessage(error), tone: 'error' });
    }
  };
  const notes = (meeting.notes ?? '')
    .split('\n')
    .map((l) => l.replace(/^[-•*]\s*/, '').trim())
    .filter(Boolean);

  return (
    <Card className="flex flex-col gap-5 p-5" data-testid="meeting-detail">
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-lg font-semibold">{meeting.title}</h3>
        <Badge tone={status.tone}>{status.label}</Badge>
      </div>
      <ul className="flex flex-col gap-2.5 text-sm">
        <li className="flex items-center gap-2.5">
          <CalendarDays aria-hidden className="size-4 text-muted" />
          {formatDate(meeting.starts_at)}
        </li>
        <li className="flex items-center gap-2.5">
          <Clock aria-hidden className="size-4 text-muted" />
          {formatTime(meeting.starts_at)} – {formatTime(meeting.ends_at)}
        </li>
        {meeting.platform ? (
          <li className="flex items-center gap-2.5">
            <Video aria-hidden className="size-4 text-muted" />
            {meeting.location?.startsWith('http') ? (
              <a className="link" href={meeting.location} target="_blank" rel="noreferrer noopener">
                {PLATFORMS.find((p) => p.value === meeting.platform)?.label}
              </a>
            ) : (
              <>
                {PLATFORMS.find((p) => p.value === meeting.platform)?.label}
                {meeting.location ? ` · ${meeting.location}` : ''}
              </>
            )}
          </li>
        ) : null}
      </ul>
      <div className="border-t border-line-soft pt-4">
        <div className="mb-2 text-sm font-semibold">Attendees ({meeting.attendees.length})</div>
        <Attendees meeting={meeting} max={6} />
      </div>
      {meeting.agenda ? (
        <div>
          <div className="mb-1.5 text-sm font-semibold">Agenda</div>
          <p className="text-[13px] whitespace-pre-wrap text-muted">{meeting.agenda}</p>
        </div>
      ) : null}
      <div>
        <div className="mb-1.5 text-sm font-semibold">Meeting Notes</div>
        {notes.length ? (
          <ul className="list-disc pl-5 text-[13px] text-muted">
            {notes.map((n, i) => (
              <li key={i}>{n}</li>
            ))}
          </ul>
        ) : (
          <p className="text-[13px] text-muted">
            {meeting.status === 'cancelled'
              ? `Cancelled${meeting.cancelled_reason ? `: ${meeting.cancelled_reason}` : '.'}`
              : 'No notes yet.'}
          </p>
        )}
      </div>
      <div>
        <div className="mb-2 text-sm font-semibold">Next Actions</div>
        <ul className="flex flex-col gap-2.5" data-testid="action-items">
          {meeting.action_items.map((i) => (
            <li key={i.id} className="flex items-center gap-2.5 text-[13px]">
              <button
                type="button"
                aria-label={i.done ? `Mark "${i.title}" not done` : `Mark "${i.title}" done`}
                className="cursor-pointer"
                onClick={() =>
                  void run(() => meetingsApi.updateActionItem(i.id, { done: !i.done }))
                }
              >
                {i.done ? (
                  <CircleCheck aria-hidden className="size-5 text-ok" />
                ) : (
                  <Circle aria-hidden className="size-5 text-muted" />
                )}
              </button>
              <span className={cn('flex-1', i.done && 'text-muted line-through')}>
                {i.title}
                {i.owner ? (
                  <span className="block text-xs text-muted">{i.owner.full_name}</span>
                ) : null}
              </span>
              <span className="text-xs whitespace-nowrap text-muted">
                {i.due_date ? formatDate(i.due_date) : ''}
              </span>
              {meeting.can_manage ? (
                <button
                  type="button"
                  aria-label={`Delete "${i.title}"`}
                  className="cursor-pointer text-faint hover:text-bad"
                  onClick={() => void run(() => meetingsApi.deleteActionItem(i.id))}
                >
                  <Trash2 aria-hidden className="size-3.5" />
                </button>
              ) : null}
            </li>
          ))}
          {!meeting.action_items.length ? (
            <li className="text-[13px] text-muted">None yet.</li>
          ) : null}
        </ul>
        {meeting.can_manage ? (
          <form
            className="mt-3 grid gap-2"
            onSubmit={async (e) => {
              e.preventDefault();
              await run(
                () =>
                  meetingsApi.addActionItem(meeting.id, {
                    title: item,
                    owner_id: owner || null,
                    due_date: due || null,
                  }),
                'Action item added.',
              );
              setItem('');
              setOwner('');
              setDue('');
            }}
          >
            <TextField
              label="New action item"
              required
              maxLength={300}
              value={item}
              onChange={(e) => setItem(e.target.value)}
            />
            <div className="grid grid-cols-2 gap-2">
              <SelectField
                label="Owner"
                placeholder="Nobody yet"
                options={(people.data ?? []).map((p) => ({ value: p.id, label: p.full_name }))}
                value={owner}
                onChange={(e) => setOwner(e.target.value)}
              />
              <TextField
                label="Due"
                type="date"
                value={due}
                onChange={(e) => setDue(e.target.value)}
              />
            </div>
            <Button type="submit" size="sm" disabled={!item.trim()}>
              <Plus aria-hidden className="size-3.5" />
              Add action item
            </Button>
          </form>
        ) : null}
      </div>
      {meeting.can_manage && meeting.status === 'scheduled' ? (
        <div className="flex flex-wrap gap-2 border-t border-line-soft pt-4">
          <Button variant="primary" onClick={() => setCompleting(true)}>
            Complete with notes
          </Button>
          <Button onClick={onEdit}>
            Edit
            <ArrowRight aria-hidden className="size-4" />
          </Button>
          <Button
            variant="danger"
            onClick={() =>
              void run(() => meetingsApi.cancel(meeting.id, null), 'Meeting cancelled.')
            }
          >
            Cancel meeting
          </Button>
        </div>
      ) : null}
      {completing ? (
        <CompleteDialog
          meeting={meeting}
          clientId={clientId}
          onClose={() => setCompleting(false)}
        />
      ) : null}
    </Card>
  );
}

export function MeetingsTab({ client }: { client: ClientDetail }) {
  const meetings = useClientMeetings(client.id);
  const [params, setParams] = useSearchParams();
  const [selected, setSelected] = useState<string | null>(null);
  const [editor, setEditor] = useState<{ meeting: Meeting | null } | null>(
    params.get('new') ? { meeting: null } : null,
  );
  const data = meetings.data;
  const list = useMemo(() => data?.meetings ?? [], [data]);
  const current =
    list.find((m) => m.id === selected) ??
    list.find((m) => m.display_status === 'upcoming') ??
    list[list.length - 1] ??
    null;

  if (meetings.isPending) return <EmptyState title="Loading meetings…" />;
  if (!data)
    return (
      <EmptyState title="Couldn't load meetings" description="Reload the page to try again." />
    );
  const s = data.stats;
  const pct = (n: number) => (s.total ? `${Math.round((n / s.total) * 100)}% of total` : '—');

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold">Meetings</h2>
          <p className="mt-1 text-muted">Plan, track and manage all client meetings.</p>
        </div>
        {data.can_schedule ? (
          <Button variant="primary" onClick={() => setEditor({ meeting: null })}>
            <Plus aria-hidden className="size-4" />
            Schedule Meeting
          </Button>
        ) : null}
      </div>
      <div className="grid items-start gap-5 xl:grid-cols-[1fr_360px]">
        <div className="flex min-w-0 flex-col gap-5">
          <div className="grid gap-4 sm:grid-cols-2 2xl:grid-cols-4">
            <StatCard
              label="Total Meetings"
              value={s.total}
              hint="All meetings"
              icon={CalendarDays}
            />
            <StatCard
              label="Completed"
              value={s.completed}
              hint={pct(s.completed)}
              icon={CalendarCheck}
              tone="ok"
            />
            <StatCard
              label="Upcoming"
              value={s.upcoming}
              hint={pct(s.upcoming)}
              icon={CalendarClock}
              tone="warn"
            />
            <StatCard
              label="Cancelled"
              value={s.cancelled}
              hint={pct(s.cancelled)}
              icon={CalendarX}
              tone="info"
            />
          </div>
          <Panel title="Meetings List" flush>
            {list.length ? (
              <div className="overflow-x-auto">
                <table className="table" data-testid="meetings-table">
                  <thead>
                    <tr>
                      <th>Meeting</th>
                      <th>Type</th>
                      <th>Date &amp; Time</th>
                      <th>Attendees</th>
                      <th>Status</th>
                      <th className="text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {list.map((m) => {
                      const type = typeOf(m.type);
                      const status = MEETING_STATUS[m.display_status];
                      return (
                        <tr key={m.id} className={cn(current?.id === m.id && 'bg-accent-soft/30')}>
                          <td>
                            <button
                              type="button"
                              className="cursor-pointer text-left"
                              onClick={() => setSelected(m.id)}
                            >
                              <span className="block font-medium">{m.title}</span>
                              {m.description ? (
                                <span className="block max-w-56 text-xs text-muted">
                                  {m.description}
                                </span>
                              ) : null}
                            </button>
                          </td>
                          <td>
                            <Badge tone={type.tone}>{type.label}</Badge>
                          </td>
                          <td className="text-[13px] whitespace-nowrap">
                            <span className="flex items-center gap-1.5">
                              <CalendarDays aria-hidden className="size-3.5 text-muted" />
                              {formatDate(m.starts_at)}
                            </span>
                            <span className="flex items-center gap-1.5 text-muted">
                              <Clock aria-hidden className="size-3.5" />
                              {formatTime(m.starts_at)} – {formatTime(m.ends_at)}
                            </span>
                          </td>
                          <td>
                            <Attendees meeting={m} />
                          </td>
                          <td>
                            <Badge tone={status.tone}>{status.label}</Badge>
                          </td>
                          <td className="text-right">
                            <Menu
                              label={`Actions for ${m.title}`}
                              items={[
                                { label: 'View details', onSelect: () => setSelected(m.id) },
                                {
                                  label: 'Edit',
                                  hidden: !m.can_manage || m.status !== 'scheduled',
                                  onSelect: () => setEditor({ meeting: m }),
                                },
                              ]}
                            />
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <EmptyState
                title="No meetings yet"
                description="Schedule the kickoff call first. Completing it (with notes) completes onboarding step 9."
              />
            )}
            {list.length ? (
              <p className="border-t border-line-soft py-3 text-center text-[13px] text-muted">
                Showing 1 to {list.length} of {list.length} meetings
              </p>
            ) : null}
          </Panel>
        </div>
        {current ? (
          <DetailPanel
            meeting={current}
            clientId={client.id}
            onEdit={() => setEditor({ meeting: current })}
          />
        ) : null}
      </div>
      <ScheduleDrawer
        client={client}
        meeting={editor?.meeting ?? null}
        open={editor !== null}
        onClose={() => {
          setEditor(null);
          if (params.get('new'))
            setParams((p) => {
              const next = new URLSearchParams(p);
              next.delete('new');
              return next;
            });
        }}
        onSaved={setSelected}
      />
    </div>
  );
}
