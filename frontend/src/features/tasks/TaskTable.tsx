/** The demo's task table: title + code, status, assignee, client, due (red when overdue). */
import { Badge } from '@/components/ui/Badge';
import { TASK_STATUS, type TaskItem } from '@/features/tasks/api';
import { formatDate } from '@/lib/format';
import { cn } from '@/lib/utils';

export function TaskTable({
  tasks,
  onOpen,
}: {
  tasks: readonly TaskItem[];
  onOpen(id: string): void;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="table" data-testid="task-table">
        <thead>
          <tr>
            <th>Task</th>
            <th>Status</th>
            <th>Assignee</th>
            <th>Client</th>
            <th>Due</th>
          </tr>
        </thead>
        <tbody>
          {tasks.map((task) => (
            <tr key={task.id}>
              <td>
                <button
                  type="button"
                  className="link cursor-pointer text-left"
                  onClick={() => onOpen(task.id)}
                >
                  {task.title}
                </button>{' '}
                <span className="code">{task.code}</span>
              </td>
              <td>
                <Badge tone={TASK_STATUS[task.status].tone}>{task.status_label}</Badge>
              </td>
              <td>{task.assignee?.full_name ?? <span className="text-muted">Unassigned</span>}</td>
              <td>{task.client_name}</td>
              <td className={cn('font-mono text-xs tabular-nums', task.overdue && 'text-bad')}>
                {formatDate(task.due_date)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
