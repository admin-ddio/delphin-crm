/** /approvals/:id: one request, shown with its task's details and decision form. */
import { useParams } from 'react-router';

import { Alert } from '@/components/ui/Alert';
import { Badge } from '@/components/ui/Badge';
import { Panel } from '@/components/ui/Card';
import { PageHeader } from '@/components/ui/PageHeader';
import { APPROVAL_STATUS, STAGE_LABEL, useApproval } from '@/features/approvals/api';
import { useTask } from '@/features/tasks/api';
import { TaskBody } from '@/features/tasks/TaskDrawer';

const crumb = { label: 'Approvals', to: '/approvals' };

export function Component() {
  const { id = '' } = useParams();
  const approval = useApproval(id);
  const task = useTask(approval.data?.task_id ?? null);
  if (approval.isPending) return <PageHeader title="Loading…" crumb={crumb} />;
  if (!approval.data) {
    return (
      <>
        <PageHeader title="Approval not found" crumb={crumb} />
        <Alert tone="bad">This approval doesn't exist or you don't have access to it.</Alert>
      </>
    );
  }
  const data = approval.data;
  return (
    <>
      <PageHeader
        crumb={crumb}
        title={data.task_title}
        description={
          <span className="flex flex-wrap items-center gap-2">
            <span className="code">
              {data.task_code} · v{data.version}
            </span>
            · {data.client_name}
            <Badge tone="info">{STAGE_LABEL[data.stage]}</Badge>
            <Badge tone={APPROVAL_STATUS[data.status].tone}>
              {APPROVAL_STATUS[data.status].label}
            </Badge>
          </span>
        }
      />
      <Panel>
        <div className="flex flex-col gap-3.5">
          {task.data ? <TaskBody task={task.data} /> : null}
        </div>
      </Panel>
    </>
  );
}
