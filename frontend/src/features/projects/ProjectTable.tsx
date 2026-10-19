/** The demo's project table: name + code, client, manager, progress, open / overdue. */
import { Progress } from '@/components/ui/Data';
import { Link } from '@/components/ui/Link';
import type { ProjectListItem } from '@/features/projects/api';
import { cn } from '@/lib/utils';

export function ProjectTable({ projects }: { projects: readonly ProjectListItem[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="table" data-testid="projects-table">
        <thead>
          <tr>
            <th>Project</th>
            <th>Client</th>
            <th>Manager</th>
            <th>Progress</th>
            <th>Open / overdue</th>
          </tr>
        </thead>
        <tbody>
          {projects.map((project) => (
            <tr key={project.id}>
              <td>
                <Link className="link" to={`/projects/${project.id}`}>
                  {project.name}
                </Link>
                <div className="code">{project.code}</div>
              </td>
              <td>{project.client_name}</td>
              <td>{project.manager.full_name}</td>
              <td className="w-[180px]">
                <Progress value={project.stats.progress} label={`${project.name} progress`} />
              </td>
              <td className="font-mono text-xs tabular-nums">
                {project.stats.open} /{' '}
                <span className={cn(project.stats.overdue > 0 && 'text-bad')}>
                  {project.stats.overdue}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
