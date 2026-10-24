/** /tasks: "Tasks & work" (layout and wording from the clickable demo). */
import { useSearchParams } from 'react-router';

import { Panel } from '@/components/ui/Card';
import { Tabs } from '@/components/ui/Data';
import { EmptyState } from '@/components/ui/EmptyState';
import { PageHeader } from '@/components/ui/PageHeader';
import { useTasks, type TaskView } from '@/features/tasks/api';
import { TaskDrawer } from '@/features/tasks/TaskDrawer';
import { TaskTable } from '@/features/tasks/TaskTable';

const VIEWS: readonly TaskView[] = ['mine', 'review', 'all'];
const EMPTY: Record<TaskView, string> = {
  mine: 'Open tasks assigned to you appear here.',
  review: 'Tasks waiting for your internal review appear here.',
  all: 'Open tasks on projects you can see appear here.',
};

export function Component() {
  const [params, setParams] = useSearchParams();
  const requested = params.get('view') as TaskView | null;
  const view: TaskView = requested && VIEWS.includes(requested) ? requested : 'mine';
  const open = params.get('task');
  const lists = { mine: useTasks('mine'), review: useTasks('review'), all: useTasks('all') };
  const current = lists[view];

  const update = (key: string, value: string | null) =>
    setParams((existing) => {
      const next = new URLSearchParams(existing);
      if (value) next.set(key, value);
      else next.delete(key);
      return next;
    });

  const label = (text: string, key: TaskView) => (
    <>
      {text} <span className="code">{lists[key].data?.length ?? '…'}</span>
    </>
  );

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
          { key: 'mine', label: label('My tasks', 'mine') },
          { key: 'review', label: label('Awaiting my review', 'review') },
          { key: 'all', label: label('All I can see', 'all') },
        ]}
      />
      <Panel flush>
        {current.isPending ? <EmptyState title="Loading tasks…" /> : null}
        {current.isError ? (
          <EmptyState title="Couldn't load tasks" description="Reload the page to try again." />
        ) : null}
        {current.data?.length === 0 ? (
          <EmptyState title="Nothing here" description={EMPTY[view]} />
        ) : null}
        {current.data?.length ? (
          <TaskTable tasks={current.data} onOpen={(id) => update('task', id)} />
        ) : null}
      </Panel>
      <TaskDrawer taskId={open} onClose={() => update('task', null)} />
    </>
  );
}
