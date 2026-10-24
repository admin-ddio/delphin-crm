/**
 * /projects/new[?client=<id>]. Only clients whose onboarding is completed can be
 * chosen (the server enforces it too). Defaults follow the demo: "<Client> SEO
 * Retainer", starting today, with the "SEO onboarding & foundation" template.
 */
import { useEffect, useId, useState, type FormEvent } from 'react';
import { useNavigate, useSearchParams } from 'react-router';

import { Alert } from '@/components/ui/Alert';
import { Button, LinkButton } from '@/components/ui/Button';
import { Panel } from '@/components/ui/Card';
import { PageHeader } from '@/components/ui/PageHeader';
import { useToast } from '@/components/ui/Toast';
import {
  useCreateProject,
  useEligibleClients,
  useManagerOptions,
  type ProjectCreate,
} from '@/features/projects/api';
import { ApiError } from '@/lib/api-client';
import { useAuth } from '@/lib/auth-context';
import { can, P, ROLE_LABELS, type RoleKey } from '@/lib/permissions';

const crumb = { label: 'Projects', to: '/projects' };

function todayIso() {
  const d = new Date();
  return new Date(d.getTime() - d.getTimezoneOffset() * 60_000).toISOString().slice(0, 10);
}

export function Component() {
  const { actor } = useAuth();
  const allowed = can(actor?.permissions ?? [], P.projectsCreate);
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { toast } = useToast();
  const clients = useEligibleClients(allowed);
  const managers = useManagerOptions(allowed);
  const create = useCreateProject();
  const ids = {
    client: useId(),
    name: useId(),
    manager: useId(),
    start: useId(),
    template: useId(),
  };

  const [clientId, setClientId] = useState(params.get('client') ?? '');
  const [name, setName] = useState('');
  const [nameTouched, setNameTouched] = useState(false);
  const [managerId, setManagerId] = useState('');
  const [start, setStart] = useState(todayIso());
  const [template, setTemplate] = useState<ProjectCreate['template']>('seo_foundation');

  const client = clients.data?.find((c) => c.id === clientId);
  useEffect(() => {
    if (client && !nameTouched) setName(`${client.name} SEO Retainer`);
  }, [client, nameTouched]);
  useEffect(() => {
    if (managerId) return;
    const pick = managers.data?.find((m) => m.id === actor?.id) ?? managers.data?.[0];
    if (pick) setManagerId(pick.id);
  }, [managers.data, managerId, actor?.id]);

  if (!actor || !allowed) {
    const role = ROLE_LABELS[actor?.roles[0] as RoleKey] ?? 'Your role';
    return (
      <>
        <PageHeader title="New project" crumb={crumb} />
        <Alert tone="bad" title="Access denied">
          {role} can't create projects.
        </Alert>
      </>
    );
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      const project = await create.mutateAsync({
        client_id: clientId,
        name,
        manager_id: managerId,
        start_date: start,
        template,
      });
      const tasks = project.tasks.length ? ` with ${project.tasks.length} tasks` : '';
      toast({ title: `Project ${project.code} created${tasks}.` });
      navigate(`/projects/${project.id}`);
    } catch (error) {
      toast({
        title: error instanceof ApiError ? error.message : 'Something went wrong. Try again.',
        tone: 'error',
      });
    }
  }

  const requested = params.get('client');
  const requestedLocked = Boolean(
    requested && clients.data && !clients.data.some((c) => c.id === requested),
  );

  return (
    <>
      <PageHeader
        title="New project"
        crumb={crumb}
        description="Projects can only be created after client onboarding is completed. Creating the client's first project completes onboarding step 13."
      />
      {requestedLocked ? (
        <div className="mb-4">
          <Alert tone="warn" title="Project creation is locked">
            Projects can be created once onboarding is completed.
          </Alert>
        </div>
      ) : null}
      {clients.data?.length === 0 ? (
        <Alert tone="info" title="No clients ready for a project">
          Complete a client's onboarding first. Then create its project here or from the client
          page.
        </Alert>
      ) : (
        <Panel>
          <form className="flex max-w-xl flex-col gap-3" onSubmit={submit}>
            <div className="label">
              <label htmlFor={ids.client}>Client</label>
              <select
                id={ids.client}
                className="input"
                required
                value={clientId}
                onChange={(e) => setClientId(e.target.value)}
              >
                <option value="">Choose a client…</option>
                {clients.data?.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} ({c.code}){c.has_project ? ' · has a project' : ''}
                  </option>
                ))}
              </select>
            </div>
            <div className="label">
              <label htmlFor={ids.name}>Project name</label>
              <input
                id={ids.name}
                className="input"
                required
                maxLength={200}
                value={name}
                onChange={(e) => {
                  setName(e.target.value);
                  setNameTouched(true);
                }}
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="label">
                <label htmlFor={ids.manager}>Project manager</label>
                <select
                  id={ids.manager}
                  className="input"
                  required
                  value={managerId}
                  onChange={(e) => setManagerId(e.target.value)}
                >
                  {managers.data?.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.full_name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="label">
                <label htmlFor={ids.start}>Start date</label>
                <input
                  id={ids.start}
                  type="date"
                  className="input"
                  required
                  value={start}
                  onChange={(e) => setStart(e.target.value)}
                />
              </div>
            </div>
            <div className="label">
              <label htmlFor={ids.template}>Template</label>
              <select
                id={ids.template}
                className="input"
                value={template}
                onChange={(e) => setTemplate(e.target.value as ProjectCreate['template'])}
              >
                <option value="seo_foundation">SEO onboarding &amp; foundation (5 tasks)</option>
                <option value="blank">Blank project</option>
              </select>
              <span className="text-[12.5px] font-normal text-faint">
                The template adds a baseline audit, keyword research, technical roadmap, on-page
                work and the month 1 report, dated from the start date and assigned to the client's
                specialist.
              </span>
            </div>
            <div className="flex gap-2">
              <Button
                type="submit"
                variant="primary"
                disabled={create.isPending || !clientId || !managerId}
              >
                Create project
              </Button>
              <LinkButton to="/projects">Cancel</LinkButton>
            </div>
          </form>
        </Panel>
      )}
    </>
  );
}
