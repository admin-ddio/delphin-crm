/** /projects (layout and wording from the clickable demo). */
import { LinkButton } from '@/components/ui/Button';
import { Panel } from '@/components/ui/Card';
import { EmptyState } from '@/components/ui/EmptyState';
import { PageHeader } from '@/components/ui/PageHeader';
import { useProjects } from '@/features/projects/api';
import { ProjectTable } from '@/features/projects/ProjectTable';
import { useAuth } from '@/lib/auth-context';
import { can, P } from '@/lib/permissions';

export function Component() {
  const { actor } = useAuth();
  const canCreate = can(actor?.permissions ?? [], P.projectsCreate);
  const projects = useProjects();
  return (
    <>
      <PageHeader
        title="Projects"
        description="Progress is derived from completed tasks. New projects are only possible for clients whose onboarding is complete."
        actions={
          canCreate ? (
            <LinkButton to="/projects/new" variant="primary">
              New project
            </LinkButton>
          ) : null
        }
      />
      <Panel flush>
        {projects.isPending ? <EmptyState title="Loading projects…" /> : null}
        {projects.isError ? (
          <EmptyState title="Couldn't load projects" description="Reload the page to try again." />
        ) : null}
        {projects.data?.length === 0 ? (
          <EmptyState
            title="No projects yet"
            description="Complete a client's onboarding, then create its project from the client page."
          />
        ) : null}
        {projects.data?.length ? <ProjectTable projects={projects.data} /> : null}
      </Panel>
    </>
  );
}
