/** The client page's Projects tab (demo: locked callout until onboarding is completed). */
import { LinkButton } from '@/components/ui/Button';
import { Alert } from '@/components/ui/Alert';
import { Panel } from '@/components/ui/Card';
import { EmptyState } from '@/components/ui/EmptyState';
import { useOnboarding } from '@/features/onboarding/api';
import { useProjects } from '@/features/projects/api';
import { ProjectTable } from '@/features/projects/ProjectTable';
import { useAuth } from '@/lib/auth-context';
import { can, P } from '@/lib/permissions';

export function ClientProjectsTab({ clientId }: { clientId: string }) {
  const { actor } = useAuth();
  const onboarding = useOnboarding(clientId);
  const projects = useProjects(clientId);
  const locked = onboarding.data ? !onboarding.data.completed_at : true;
  const canCreate = !locked && can(actor?.permissions ?? [], P.projectsCreate);
  return (
    <div className="flex flex-col gap-3">
      {onboarding.data && locked ? (
        <Alert tone="warn" title="Project creation is locked">
          Projects can be created once onboarding is completed.
        </Alert>
      ) : null}
      <Panel
        title="Projects"
        flush
        actions={
          canCreate ? (
            <LinkButton to={`/projects/new?client=${clientId}`} variant="primary" size="sm">
              New project
            </LinkButton>
          ) : null
        }
      >
        {projects.isPending ? <EmptyState title="Loading…" /> : null}
        {projects.data?.length === 0 ? <EmptyState title="No projects yet" /> : null}
        {projects.data?.length ? <ProjectTable projects={projects.data} /> : null}
      </Panel>
    </div>
  );
}
