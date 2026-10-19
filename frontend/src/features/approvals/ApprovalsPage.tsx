/** /approvals (layout and wording from the clickable demo). */
import { useSearchParams } from 'react-router';

import { Badge } from '@/components/ui/Badge';
import { Panel } from '@/components/ui/Card';
import { EmptyState } from '@/components/ui/EmptyState';
import { PageHeader } from '@/components/ui/PageHeader';
import {
  APPROVAL_STATUS,
  STAGE_LABEL,
  useApprovals,
  type ApprovalItem,
} from '@/features/approvals/api';
import { TaskDrawer } from '@/features/tasks/TaskDrawer';
import { formatDateTime } from '@/lib/format';

export function ApprovalTable({
  rows,
  onOpen,
  testId,
}: {
  rows: readonly ApprovalItem[];
  onOpen(taskId: string): void;
  testId?: string;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="table" data-testid={testId}>
        <thead>
          <tr>
            <th>Deliverable</th>
            <th>Client</th>
            <th>Stage</th>
            <th>Version</th>
            <th>Requested by</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td>
                <button
                  type="button"
                  className="link cursor-pointer text-left"
                  onClick={() => onOpen(row.task_id)}
                >
                  {row.task_title}
                </button>
                <div className="code">
                  {row.task_code} · {formatDateTime(row.created_at)}
                </div>
              </td>
              <td>{row.client_name}</td>
              <td>
                <Badge tone="info">{STAGE_LABEL[row.stage]}</Badge>
              </td>
              <td className="font-mono text-xs tabular-nums">v{row.version}</td>
              <td>{row.requested_by?.full_name ?? '—'}</td>
              <td>
                <Badge tone={APPROVAL_STATUS[row.status].tone}>
                  {APPROVAL_STATUS[row.status].label}
                </Badge>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Component() {
  const [params, setParams] = useSearchParams();
  const mine = useApprovals('mine');
  const all = useApprovals('all');
  const open = params.get('task');
  const setTask = (taskId: string | null) =>
    setParams((current) => {
      const next = new URLSearchParams(current);
      if (taskId) next.set('task', taskId);
      else next.delete('task');
      return next;
    });

  return (
    <>
      <PageHeader
        title="Approvals"
        description="Internal reviews and client decisions. No one can approve their own submission; client decisions record who decided and how they told us."
      />
      <div className="flex flex-col gap-4">
        <Panel title="Awaiting my decision" flush>
          {mine.isPending ? <EmptyState title="Loading…" /> : null}
          {mine.data?.length === 0 ? <EmptyState title="Nothing waiting" /> : null}
          {mine.data?.length ? (
            <ApprovalTable rows={mine.data} onOpen={setTask} testId="approvals-mine" />
          ) : null}
        </Panel>
        <Panel title="All requests" flush>
          {all.isPending ? <EmptyState title="Loading…" /> : null}
          {all.data?.length === 0 ? <EmptyState title="Nothing waiting" /> : null}
          {all.data?.length ? (
            <ApprovalTable rows={all.data} onOpen={setTask} testId="approvals-all" />
          ) : null}
        </Panel>
      </div>
      <TaskDrawer taskId={open} onClose={() => setTask(null)} />
    </>
  );
}
