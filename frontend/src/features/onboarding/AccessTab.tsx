/**
 * Screen 5 – Access Checklist (product mockup): overall progress, request access,
 * per-platform requested / received / verified dates, status, verification owner,
 * notes and actions; add custom items; never stores credentials.
 */
import {
  BarChart3,
  CircleCheck,
  HardDrive,
  KeyRound,
  LayoutTemplate,
  Lightbulb,
  Link2,
  Plus,
  Search,
  Send,
  ShieldCheck,
  type LucideIcon,
} from 'lucide-react';
import { useId, useState, type FormEvent } from 'react';

import { Avatar } from '@/components/ui/Avatar';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Dialog } from '@/components/ui/Dialog';
import { EmptyState } from '@/components/ui/EmptyState';
import { TextField } from '@/components/ui/Field';
import { TextAreaField } from '@/components/ui/Fields';
import { Menu } from '@/components/ui/Menu';
import { Ring } from '@/components/ui/Ring';
import { useToast } from '@/components/ui/Toast';
import {
  ACCESS_STATUS,
  onboardingApi,
  useOnboarding,
  useOnboardingAction,
  type AccessItem,
  type OnboardingDetail,
} from '@/features/onboarding/api';
import { ApiError } from '@/lib/api-client';
import { formatDate } from '@/lib/format';
import { cn } from '@/lib/utils';

const LOGOS: Record<string, [LucideIcon, string]> = {
  GSC: [Search, 'bg-[#e8f0fe] text-[#1a73e8]'],
  GA4: [BarChart3, 'bg-[#fff1d6] text-[#e37400]'],
  CMS: [LayoutTemplate, 'bg-[#e8f0fe] text-[#2a62d8]'],
  AHREFS: [Link2, 'bg-[#e6effd] text-[#1d4ed8]'],
  GDRIVE: [HardDrive, 'bg-[#e6f6ec] text-[#1f8a4c]'],
};

function Logo({ item }: { item: AccessItem }) {
  const [Icon, tone] = LOGOS[item.key] ?? [KeyRound, 'bg-accent-soft text-accent'];
  return (
    <span
      className={cn('grid size-10 shrink-0 place-items-center rounded-lg border border-line', tone)}
    >
      <Icon aria-hidden className="size-5" />
    </span>
  );
}

function NotesDialog({
  item,
  clientId,
  onClose,
}: {
  item: AccessItem | null;
  clientId: string;
  onClose(): void;
}) {
  const action = useOnboardingAction(clientId);
  const { toast } = useToast();
  const [notes, setNotes] = useState(item?.notes ?? '');
  if (!item) return null;
  return (
    <Dialog
      open
      onClose={onClose}
      title={`${item.label} notes`}
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button
            variant="primary"
            disabled={action.isPending}
            onClick={async () => {
              try {
                await action.mutateAsync(() =>
                  onboardingApi.accessNotes(clientId, item.key, notes || null),
                );
                toast({ title: 'Notes saved.' });
                onClose();
              } catch (error) {
                toast({
                  title: error instanceof ApiError ? error.message : 'Something went wrong.',
                  tone: 'error',
                });
              }
            }}
          >
            Save notes
          </Button>
        </>
      }
    >
      <TextAreaField
        label="Notes"
        hint="Who shared it, which property/account, follow-ups. Never paste passwords."
        maxLength={2000}
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
      />
    </Dialog>
  );
}

function AddItemDialog({
  open,
  clientId,
  onClose,
}: {
  open: boolean;
  clientId: string;
  onClose(): void;
}) {
  const action = useOnboardingAction(clientId);
  const { toast } = useToast();
  const formId = useId();
  const [label, setLabel] = useState('');
  const [description, setDescription] = useState('');
  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      await action.mutateAsync(() => onboardingApi.addAccess(clientId, label, description || null));
      toast({ title: `${label} added to the checklist.` });
      setLabel('');
      setDescription('');
      onClose();
    } catch (error) {
      toast({
        title: error instanceof ApiError ? error.message : 'Something went wrong.',
        tone: 'error',
      });
    }
  }
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Add access item"
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button type="submit" form={formId} variant="primary" disabled={action.isPending}>
            Add item
          </Button>
        </>
      }
    >
      <form id={formId} onSubmit={submit} className="flex flex-col gap-3">
        <TextField
          label="Access *"
          required
          maxLength={100}
          value={label}
          onChange={(e) => setLabel(e.target.value)}
        />
        <TextField
          label="Description"
          maxLength={300}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
      </form>
    </Dialog>
  );
}

function RowActions({
  item,
  data,
  clientId,
}: {
  item: AccessItem;
  data: OnboardingDetail;
  clientId: string;
}) {
  const action = useOnboardingAction(clientId);
  const { toast } = useToast();
  const [notes, setNotes] = useState(false);
  const { manage, verify_access: verify } = data.permissions;
  const set = (status: AccessItem['status'], done: string) => async () => {
    try {
      await action.mutateAsync(() => onboardingApi.access(clientId, item.key, status));
      toast({ title: done });
    } catch (error) {
      toast({
        title: error instanceof ApiError ? error.message : 'Something went wrong.',
        tone: 'error',
      });
    }
  };
  const s = item.status;
  return (
    <>
      <Menu
        label={`Actions for ${item.label}`}
        items={[
          {
            label: 'Mark requested',
            hidden: !manage || s !== 'pending',
            onSelect: set('requested', `${item.label} requested.`),
          },
          {
            label: 'Mark received',
            hidden: !manage || !['pending', 'requested', 'rejected'].includes(s),
            onSelect: set('received', `${item.label} received.`),
          },
          {
            label: 'Verify',
            hidden: !verify || s !== 'received',
            onSelect: set('verified', `${item.label} verified.`),
          },
          {
            label: 'Reject',
            hidden: !verify || s !== 'received',
            danger: true,
            onSelect: set('rejected', `${item.label} rejected.`),
          },
          {
            label: 'Not required',
            hidden: !manage || !['pending', 'requested', 'rejected'].includes(s),
            onSelect: set('not_required', `${item.label} marked not required.`),
          },
          {
            label: 'Required again',
            hidden: !manage || s !== 'not_required',
            onSelect: set('pending', `${item.label} is required again.`),
          },
          {
            label: item.notes ? 'Edit notes' : 'Add notes',
            hidden: !manage && !verify,
            onSelect: () => setNotes(true),
          },
          {
            label: 'Remove',
            danger: true,
            hidden: !manage || !item.is_custom || s === 'verified',
            onSelect: async () => {
              try {
                await action.mutateAsync(() => onboardingApi.deleteAccess(clientId, item.key));
                toast({ title: `${item.label} removed.` });
              } catch (error) {
                toast({
                  title: error instanceof ApiError ? error.message : 'Something went wrong.',
                  tone: 'error',
                });
              }
            },
          },
        ]}
      />
      {notes ? (
        <NotesDialog item={item} clientId={clientId} onClose={() => setNotes(false)} />
      ) : null}
    </>
  );
}

export function AccessTab({ clientId }: { clientId: string }) {
  const onboarding = useOnboarding(clientId);
  const action = useOnboardingAction(clientId);
  const { toast } = useToast();
  const [adding, setAdding] = useState(false);
  const data = onboarding.data;
  if (!data) return <EmptyState title="Loading access checklist…" />;
  const summary = data.access_summary;
  const manage = data.permissions.manage;
  const pending = data.access.some((a) => a.status === 'pending');
  const waiting = data.access.some((a) => a.status === 'pending' || a.status === 'requested');
  const bulk = (status: 'requested' | 'received', done: string) => async () => {
    try {
      await action.mutateAsync(() => onboardingApi.bulkAccess(clientId, status));
      toast({ title: done });
    } catch (error) {
      toast({
        title: error instanceof ApiError ? error.message : 'Something went wrong.',
        tone: 'error',
      });
    }
  };

  return (
    <div className="flex flex-col gap-5">
      <Card className="flex flex-wrap items-start justify-between gap-5 p-6">
        <div className="min-w-[240px] flex-1">
          <h2 className="text-xl font-bold">Access Checklist</h2>
          <p className="mt-1 text-muted">
            Collect and verify all required access to kickstart the project.
          </p>
          {data.locked_reason && !data.completed_at ? (
            <p className="mt-2 text-sm text-warn">{data.locked_reason}</p>
          ) : null}
        </div>
        <div
          className="flex items-center gap-6 rounded-xl border border-line px-5 py-4"
          data-testid="access-progress"
        >
          <div>
            <div className="text-sm font-medium">Overall Progress</div>
            <div className="text-[26px] font-bold text-ok">{summary.percent}%</div>
            <div className="text-[13px] text-muted">
              {summary.verified} of {summary.required} access verified
            </div>
          </div>
          <Ring value={summary.percent} size={56} stroke={7} tone="ok" label="Access verified">
            <span />
          </Ring>
        </div>
        {manage ? (
          <div className="flex flex-col gap-2">
            {pending ? (
              <Button variant="primary" onClick={bulk('requested', 'Access requested.')}>
                <Send aria-hidden className="size-4" />
                Request Access
              </Button>
            ) : null}
            {waiting ? (
              <Button onClick={bulk('received', 'All waiting access marked as received.')}>
                Mark all received
              </Button>
            ) : null}
          </div>
        ) : null}
      </Card>

      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="table" data-testid="access-table">
            <thead>
              <tr>
                <th>Access</th>
                <th>Description</th>
                <th>Requested On</th>
                <th>Received On</th>
                <th>Verified On</th>
                <th>Status</th>
                <th>Verified By</th>
                <th className="text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {data.access.map((item) => (
                <tr key={item.key}>
                  <td>
                    <div className="flex items-center gap-3">
                      <Logo item={item} />
                      <div>
                        <div className="font-medium">{item.label}</div>
                        {item.notes ? (
                          <div className="max-w-56 truncate text-xs text-muted">{item.notes}</div>
                        ) : null}
                      </div>
                    </div>
                  </td>
                  <td className="max-w-60 text-[13px] text-muted">{item.description ?? '—'}</td>
                  <td className="whitespace-nowrap">
                    {item.requested_at ? formatDate(item.requested_at) : '—'}
                  </td>
                  <td className="whitespace-nowrap">
                    {item.received_at ? formatDate(item.received_at) : '—'}
                  </td>
                  <td className="whitespace-nowrap">
                    {item.verified_at ? formatDate(item.verified_at) : '—'}
                  </td>
                  <td>
                    <Badge tone={ACCESS_STATUS[item.status].tone}>
                      {item.status === 'verified' ? (
                        <CircleCheck aria-hidden className="size-3.5" />
                      ) : null}
                      {ACCESS_STATUS[item.status].label}
                    </Badge>
                  </td>
                  <td>
                    {item.verified_by ? (
                      <span className="flex items-center gap-2">
                        <Avatar name={item.verified_by.full_name} size="xs" />
                        {item.verified_by.full_name}
                      </span>
                    ) : (
                      '—'
                    )}
                  </td>
                  <td className="text-right">
                    <RowActions item={item} data={data} clientId={clientId} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {manage ? (
        <Card className="flex flex-wrap items-center justify-between gap-3 bg-accent-soft/30 px-5 py-4">
          <div className="flex items-center gap-3">
            <span className="grid size-10 place-items-center rounded-lg bg-accent-soft text-accent">
              <Lightbulb aria-hidden className="size-5" />
            </span>
            <div>
              <div className="text-sm font-semibold">Need something else?</div>
              <div className="text-[13px] text-muted">
                If any other access is required, you can add it to the checklist.
              </div>
            </div>
          </div>
          <Button className="border-accent text-accent" onClick={() => setAdding(true)}>
            <Plus aria-hidden className="size-4" />
            Add Access Item
          </Button>
        </Card>
      ) : null}
      <Card className="flex items-center gap-3 bg-ok-soft/40 px-5 py-4 text-sm">
        <ShieldCheck aria-hidden className="size-6 text-ok" />
        <span>
          <b>Security First</b>{' '}
          <span className="text-muted">
            Only the fact that access was shared is tracked here. Never store passwords or keys in
            notes.
          </span>
        </span>
      </Card>
      <AddItemDialog open={adding} clientId={clientId} onClose={() => setAdding(false)} />
    </div>
  );
}
