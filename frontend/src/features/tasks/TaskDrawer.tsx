/**
 * Task drawer and New task drawer (layout and wording from the clickable demo).
 * Buttons come from the server's permissions.next_statuses, so the UI never offers
 * a move the API would refuse. Review submission arrives with the approvals module.
 */
import { useEffect, useId, useState, type FormEvent } from 'react';

import { Badge } from '@/components/ui/Badge';
import { Button, type ButtonVariant } from '@/components/ui/Button';
import { KeyValue } from '@/components/ui/Data';
import { Drawer } from '@/components/ui/Dialog';
import { Link } from '@/components/ui/Link';
import { useToast } from '@/components/ui/Toast';
import {
  TASK_STATUS,
  useAssigneeOptions,
  useCreateTask,
  useMoveTask,
  useTask,
  useUpdateTask,
  type TaskDetail,
  type TaskStatus,
} from '@/features/tasks/api';
import { ApiError } from '@/lib/api-client';
import { formatDate } from '@/lib/format';

function errorMessage(error: unknown) {
  return error instanceof ApiError ? error.message : 'Something went wrong. Try again.';
}

function moveLabel(task: TaskDetail, to: TaskStatus): [string, ButtonVariant] {
  switch (to) {
    case 'in_progress':
      return [task.status === 'blocked' ? 'Resume work' : 'Start work', 'primary'];
    case 'completed':
      return ['Mark completed', 'primary'];
    case 'blocked':
      return ['Mark blocked', 'secondary'];
    case 'ready':
      return ['Back to ready', 'secondary'];
    case 'backlog':
      return [task.status === 'cancelled' ? 'Reopen' : 'Move to backlog', 'secondary'];
    case 'cancelled':
      return ['Cancel task', 'danger'];
    default:
      return [TASK_STATUS[to].label, 'secondary'];
  }
}

function workflowText(task: TaskDetail) {
  const stages = [
    task.requires_review ? 'Internal review' : null,
    task.requires_client_approval ? 'Client approval' : null,
  ].filter(Boolean);
  return stages.length ? stages.join(' → ') : 'No review';
}

function ManageForm({ task }: { task: TaskDetail }) {
  const assignees = useAssigneeOptions();
  const update = useUpdateTask(task.id);
  const { toast } = useToast();
  const assigneeId = useId();
  const dueId = useId();
  const [assignee, setAssignee] = useState(task.assignee?.id ?? '');
  const [due, setDue] = useState(task.due_date ?? '');
  useEffect(() => {
    setAssignee(task.assignee?.id ?? '');
    setDue(task.due_date ?? '');
  }, [task.assignee?.id, task.due_date]);

  const dirty = assignee !== (task.assignee?.id ?? '') || due !== (task.due_date ?? '');
  async function save(event: FormEvent) {
    event.preventDefault();
    try {
      await update.mutateAsync({ assignee_id: assignee || null, due_date: due || null });
      toast({ title: 'Task updated.' });
    } catch (error) {
      toast({ title: errorMessage(error), tone: 'error' });
    }
  }
  return (
    <form className="flex flex-wrap items-end gap-2" onSubmit={save}>
      <div className="label">
        <label htmlFor={assigneeId}>Assign to</label>
        <select
          id={assigneeId}
          className="input"
          value={assignee}
          onChange={(e) => setAssignee(e.target.value)}
        >
          <option value="">Unassigned</option>
          {assignees.data?.map((person) => (
            <option key={person.id} value={person.id}>
              {person.full_name}
            </option>
          ))}
        </select>
      </div>
      <div className="label">
        <label htmlFor={dueId}>Due date</label>
        <input
          id={dueId}
          type="date"
          className="input"
          value={due}
          onChange={(e) => setDue(e.target.value)}
        />
      </div>
      <Button type="submit" size="sm" disabled={!dirty || update.isPending}>
        Save
      </Button>
    </form>
  );
}

/** The task's details and actions; used by the drawer and the /tasks/:id page. */
export function TaskBody({ task }: { task: TaskDetail }) {
  const move = useMoveTask(task.id);
  const { toast } = useToast();
  const { next_statuses: next, work, manage } = task.permissions;
  const closed = task.status === 'completed' || task.status === 'cancelled';
  const waitingForReview =
    work &&
    task.status === 'in_progress' &&
    (task.requires_review || task.requires_client_approval);

  async function go(to: TaskStatus) {
    try {
      const updated = await move.mutateAsync(to);
      toast({ title: `Moved to ${TASK_STATUS[updated.status].label}.` });
    } catch (error) {
      toast({ title: errorMessage(error), tone: 'error' });
    }
  }

  return (
    <>
      <div className="flex flex-wrap gap-2">
        <Badge tone={TASK_STATUS[task.status].tone}>{task.status_label}</Badge>
        {task.overdue ? <Badge tone="bad">Overdue</Badge> : null}
      </div>
      <KeyValue
        items={[
          [
            'Project',
            <Link key="p" className="link" to={`/projects/${task.project_id}`}>
              {task.project_name}
            </Link>,
          ],
          ['Assignee', task.assignee?.full_name ?? 'Unassigned'],
          ['Reviewer', task.reviewer?.full_name ?? '—'],
          ['Due', formatDate(task.due_date)],
          ['Workflow', workflowText(task)],
          ...(task.description ? [['Description', task.description] as [string, string]] : []),
          ...(task.completed_at
            ? [['Completed', formatDate(task.completed_at)] as [string, string]]
            : []),
        ]}
      />
      {manage && !closed ? <ManageForm task={task} /> : null}
      {next.length ? (
        <div className="flex flex-wrap gap-2" data-testid="task-actions">
          {next.map((to) => {
            const [label, variant] = moveLabel(task, to);
            return (
              <Button
                key={to}
                variant={variant}
                disabled={move.isPending}
                onClick={() => void go(to)}
              >
                {label}
              </Button>
            );
          })}
        </div>
      ) : !work && !closed ? (
        <p className="text-muted">
          Only the assignee or the project manager can work on this task.
        </p>
      ) : null}
      {waitingForReview ? (
        <p className="text-[13px] text-muted">
          This task requires review, so it can't be marked completed directly. Submitting it for
          review arrives with the Approvals module.
        </p>
      ) : null}
      <div>
        <h3 className="mb-1 text-sm font-semibold">Versions &amp; feedback</h3>
        <p className="text-muted">Nothing submitted yet.</p>
      </div>
    </>
  );
}

export function TaskDrawer({ taskId, onClose }: { taskId: string | null; onClose(): void }) {
  const task = useTask(taskId);
  const data = task.data;
  return (
    <Drawer
      open={Boolean(taskId)}
      onClose={onClose}
      title={data?.title ?? (task.isError ? 'Task not found' : 'Loading…')}
      eyebrow={data ? `${data.code} · ${data.client_name}` : null}
    >
      {task.isError ? <p className="text-muted">{errorMessage(task.error)}</p> : null}
      {data ? <TaskBody task={data} /> : null}
    </Drawer>
  );
}

function plusDays(days: number) {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

export function NewTaskDrawer({
  projectId,
  open,
  onClose,
  onCreated,
}: {
  projectId: string;
  open: boolean;
  onClose(): void;
  onCreated?(taskId: string): void;
}) {
  const assignees = useAssigneeOptions(open);
  const create = useCreateTask();
  const { toast } = useToast();
  const ids = { title: useId(), assignee: useId(), due: useId(), review: useId(), client: useId() };
  const [title, setTitle] = useState('');
  const [assignee, setAssignee] = useState('');
  const [due, setDue] = useState(plusDays(7));
  const [review, setReview] = useState(true);
  const [clientApproval, setClientApproval] = useState(false);

  useEffect(() => {
    if (!open) return;
    setTitle('');
    setAssignee('');
    setDue(plusDays(7));
    setReview(true);
    setClientApproval(false);
  }, [open]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      const task = await create.mutateAsync({
        project_id: projectId,
        title,
        assignee_id: assignee || null,
        due_date: due || null,
        requires_review: review,
        requires_client_approval: clientApproval,
      });
      toast({ title: `Task ${task.code} created.` });
      onClose();
      onCreated?.(task.id);
    } catch (error) {
      toast({ title: errorMessage(error), tone: 'error' });
    }
  }

  return (
    <Drawer open={open} onClose={onClose} title="New task">
      <form className="flex flex-col gap-3" onSubmit={submit}>
        <div className="label">
          <label htmlFor={ids.title}>Title</label>
          <input
            id={ids.title}
            className="input"
            required
            maxLength={200}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="label">
            <label htmlFor={ids.assignee}>Assignee</label>
            <select
              id={ids.assignee}
              className="input"
              value={assignee}
              onChange={(e) => setAssignee(e.target.value)}
            >
              <option value="">Unassigned</option>
              {assignees.data?.map((person) => (
                <option key={person.id} value={person.id}>
                  {person.full_name}
                </option>
              ))}
            </select>
          </div>
          <div className="label">
            <label htmlFor={ids.due}>Due date</label>
            <input
              id={ids.due}
              type="date"
              className="input"
              value={due}
              onChange={(e) => setDue(e.target.value)}
            />
          </div>
        </div>
        <label htmlFor={ids.review} className="flex items-center gap-2 text-[13px]">
          <input
            id={ids.review}
            type="checkbox"
            checked={review}
            onChange={(e) => setReview(e.target.checked)}
          />
          Requires internal review
        </label>
        <label htmlFor={ids.client} className="flex items-center gap-2 text-[13px]">
          <input
            id={ids.client}
            type="checkbox"
            checked={clientApproval}
            onChange={(e) => setClientApproval(e.target.checked)}
          />
          Requires client approval
        </label>
        <div>
          <Button type="submit" variant="primary" disabled={create.isPending}>
            Create task
          </Button>
        </div>
      </form>
    </Drawer>
  );
}
