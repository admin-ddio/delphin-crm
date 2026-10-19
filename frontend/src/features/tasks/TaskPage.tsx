/** /tasks/:id: a task on its own page (same body as the drawer). */
import { useParams } from 'react-router';

import { Alert } from '@/components/ui/Alert';
import { Panel } from '@/components/ui/Card';
import { PageHeader } from '@/components/ui/PageHeader';
import { useTask } from '@/features/tasks/api';
import { TaskBody } from '@/features/tasks/TaskDrawer';

const crumb = { label: 'Tasks & work', to: '/tasks' };

export function Component() {
  const { id = '' } = useParams();
  const task = useTask(id);
  if (task.isPending) return <PageHeader title="Loading…" crumb={crumb} />;
  if (!task.data) {
    return (
      <>
        <PageHeader title="Task not found" crumb={crumb} />
        <Alert tone="bad">This task doesn't exist or you don't have access to it.</Alert>
      </>
    );
  }
  const data = task.data;
  return (
    <>
      <PageHeader
        title={data.title}
        crumb={crumb}
        description={
          <>
            <span className="code">{data.code}</span> · {data.client_name}
          </>
        }
      />
      <Panel>
        <div className="flex flex-col gap-3.5">
          <TaskBody task={data} />
        </div>
      </Panel>
    </>
  );
}
