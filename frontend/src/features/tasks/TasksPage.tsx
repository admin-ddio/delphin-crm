/**
 * /tasks: "Tasks & work" (layout and wording from the clickable demo). The
 * "Awaiting my review" tab arrives with the approvals module.
 */
import { useSearchParams } from 'react-router';

import { Panel } from '@/components/ui/Card';
import { Tabs } from '@/components/ui/Data';
import { EmptyState } from '@/components/ui/EmptyState';
import { PageHeader } from '@/components/ui/PageHeader';
import { useTasks, type TaskView } from '@/features/tasks/api';
import { TaskDrawer } from '@/features/tasks/TaskDrawer';
import { TaskTable } from '@/features/tasks/TaskTable';

export function Component() {
  const [params, setParams] = useSearchParams();
  const view: TaskView = params.get('view') === 'all' ? 'all' : 'mine';
  const open = params.get('task');
  const mine = useTasks('mine');
  const all = useTasks('all');
  const current = view === 'mine' ? mine : all;

  const update = (key: string, value: string | null) =>
    setParams((existing) => {
      const next = new URLSearchParams(existing);
      if (value) next.set(key, value);
      else next.delete(key);
      return next;
    });

  return (
    <>
      <PageHeader
        title="Tasks & work"
        description="One task system across every project. Status changes follow the workflow: work that needs review can't be marked completed directly."
      />
      <Tabs
        label="Task views"
        value={view}
        onChange={(key) => update('view', key === 'mine' ? null : key)}
        items={[
          {
            key: 'mine',
            label: (
              <>
                My tasks <span className="code">{mine.data?.length ?? '…'}</span>
              </>
            ),
          },
          {
            key: 'all',
            label: (
              <>
                All I can see <span className="code">{all.data?.length ?? '…'}</span>
              </>
            ),
          },
        ]}
      />
      <Panel flush>
        {current.isPending ? <EmptyState title="Loading tasks…" /> : null}
        {current.isError ? (
          <EmptyState title="Couldn't load tasks" description="Reload the page to try again." />
        ) : null}
        {current.data?.length === 0 ? (
          <EmptyState
            title="Nothing here"
            description={
              view === 'mine'
                ? 'Open tasks assigned to you appear here.'
                : 'Open tasks on projects you can see appear here.'
            }
          />
        ) : null}
        {current.data?.length ? (
          <TaskTable tasks={current.data} onOpen={(id) => update('task', id)} />
        ) : null}
      </Panel>
      <TaskDrawer taskId={open} onClose={() => update('task', null)} />
    </>
  );
}
