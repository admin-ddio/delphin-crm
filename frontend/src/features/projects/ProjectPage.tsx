/**
 * /projects/:id: stats tiles and the 7-column task board (layout from the
 * clickable demo). Cards open the task drawer; ?task=<id> keeps it linkable.
 */
import { useState } from 'react';
import { useParams, useSearchParams } from 'react-router';

import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { StatCard } from '@/components/ui/Card';
import { PageHeader } from '@/components/ui/PageHeader';
import { useProject, type ProjectDetail } from '@/features/projects/api';
import { BOARD_COLUMNS, TASK_STATUS } from '@/features/tasks/api';
import { NewTaskDrawer, TaskDrawer } from '@/features/tasks/TaskDrawer';
import { Link } from '@/components/ui/Link';
import { ApiError } from '@/lib/api-client';
import { formatDate } from '@/lib/format';
import { cn } from '@/lib/utils';

const crumb = { label: 'Projects', to: '/projects' };

function Board({ project, onOpen }: { project: ProjectDetail; onOpen(id: string): void }) {
  return (
    <div className="flex gap-2.5 overflow-x-auto pb-2" data-testid="task-board">
      {BOARD_COLUMNS.map((status) => {
        const tasks = project.tasks.filter((t) => t.status === status);
        const label = TASK_STATUS[status].label;
        return (
          <section
            key={status}
            aria-label={label}
            className="flex flex-[0_0_220px] flex-col gap-2 rounded-lg bg-sunk p-2"
          >
            <h3 className="flex justify-between px-1 py-0.5 text-[11px] tracking-[.06em] text-muted uppercase">
              {label}
              <span>{tasks.length}</span>
            </h3>
            {tasks.map((task) => (
              <button
                key={task.id}
                type="button"
                onClick={() => onOpen(task.id)}
                className={cn(
                  'cursor-pointer rounded-md border border-l-[3px] border-line bg-surface px-2.5 py-2 text-left hover:border-accent',
                  task.overdue ? 'border-l-bad' : 'border-l-accent',
                )}
              >
                <div className="font-medium">{task.title}</div>
                <div className="mt-[3px] text-[11.5px] text-muted">
                  {task.code} · {task.assignee?.full_name ?? 'Unassigned'} · due{' '}
                  {formatDate(task.due_date)}
                </div>
              </button>
            ))}
          </section>
        );
      })}
    </div>
  );
}

export function Component() {
  const { id = '' } = useParams();
  const [params, setParams] = useSearchParams();
  const [creating, setCreating] = useState(false);
  const project = useProject(id);
  const openTask = params.get('task');
  const setTask = (taskId: string | null) =>
    setParams((current) => {
      const next = new URLSearchParams(current);
      if (taskId) next.set('task', taskId);
      else next.delete('task');
      return next;
    });

  if (project.isPending) return <PageHeader title="Loading…" crumb={crumb} />;
  if (project.isError || !project.data) {
    const notFound = project.error instanceof ApiError && project.error.status === 404;
    return (
      <>
        <PageHeader title={notFound ? 'Project not found' : 'Something went wrong'} crumb={crumb} />
        <Alert tone="bad">
          {notFound
            ? "This project doesn't exist or you don't have access to it."
            : "Couldn't load this project. Reload the page to try again."}
        </Alert>
      </>
    );
  }

  const data = project.data;
  const stats = data.stats;
  const cancelled = data.tasks.filter((t) => t.status === 'cancelled').length;
  return (
    <>
      <PageHeader
        crumb={crumb}
        title={data.name}
        description={
          <>
            <span className="code">{data.code}</span> ·{' '}
            <Link className="link" to={`/clients/${data.client_id}`}>
              {data.client_name}
            </Link>{' '}
            · PM: {data.manager.full_name} · Starts {formatDate(data.start_date)}
          </>
        }
        actions={
          data.can_create_tasks ? (
            <Button variant="primary" onClick={() => setCreating(true)}>
              New task
            </Button>
          ) : null
        }
      />
      <div
        className="mb-4 grid grid-cols-[repeat(auto-fit,minmax(150px,1fr))] gap-4"
        data-testid="project-stats"
      >
        <StatCard
          label="Completion"
          value={`${stats.progress}%`}
          hint="Completed ÷ non-cancelled tasks"
        />
        <StatCard
          label="Tasks"
          value={stats.tasks}
          hint={cancelled ? `${cancelled} cancelled not counted` : undefined}
        />
        <StatCard label="Overdue" value={stats.overdue} alert={stats.overdue > 0} />
        <StatCard label="In review" value={stats.in_review} />
      </div>
      <Board project={data} onOpen={setTask} />
      <TaskDrawer taskId={openTask} onClose={() => setTask(null)} />
      <NewTaskDrawer
        projectId={data.id}
        open={creating}
        onClose={() => setCreating(false)}
        onCreated={setTask}
      />
    </>
  );
}
