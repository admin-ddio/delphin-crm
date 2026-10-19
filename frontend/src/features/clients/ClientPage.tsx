/**
 * /clients/:id and its tab routes (/clients/:id/<tab>). One component renders the
 * shared header + tab bar; the tab comes from the URL. Ported so far: Overview,
 * Edit, Activity. The other pilot tabs show their "not yet ported" state here.
 */
import { NavLink, useLocation, useNavigate, useParams } from 'react-router';

import { Alert } from '@/components/ui/Alert';
import { Badge } from '@/components/ui/Badge';
import { LinkButton } from '@/components/ui/Button';
import { Panel } from '@/components/ui/Card';
import { KeyValue, Timeline } from '@/components/ui/Data';
import { EmptyState } from '@/components/ui/EmptyState';
import { PageHeader } from '@/components/ui/PageHeader';
import { useToast } from '@/components/ui/Toast';
import {
  useClient,
  useClientActivity,
  useUpdateClient,
  type ClientDetail,
} from '@/features/clients/api';
import { ClientForm, toClientBody, type ClientFormValues } from '@/features/clients/ClientForm';
import { useOnboarding } from '@/features/onboarding/api';
import { OnboardingTab } from '@/features/onboarding/OnboardingTab';
import { useProjects } from '@/features/projects/api';
import { ClientProjectsTab } from '@/features/projects/ClientProjectsTab';
import { Link } from '@/components/ui/Link';
import { STATUS_TONE } from '@/features/clients/ClientsListPage';
import { ApiError } from '@/lib/api-client';
import { useAuth } from '@/lib/auth-context';
import { can, P } from '@/lib/permissions';
import { formatDate, formatDateTime } from '@/lib/format';
import { cn } from '@/lib/utils';

/** Pilot client tabs (scaffold brief §7), in the pilot's route order. */
const TABS: { slug: string; label: string }[] = [
  { slug: '', label: 'Overview' },
  { slug: 'contacts', label: 'Contacts' },
  { slug: 'onboarding', label: 'Onboarding' },
  { slug: 'projects', label: 'Projects' },
  { slug: 'tasks', label: 'Tasks' },
  { slug: 'services', label: 'Services' },
  { slug: 'kpis', label: 'KPIs' },
  { slug: 'meetings', label: 'Meetings' },
  { slug: 'communications', label: 'Communications' },
  { slug: 'documents', label: 'Documents' },
  { slug: 'approvals', label: 'Approvals' },
  { slug: 'billing', label: 'Billing' },
  { slug: 'activity', label: 'Activity' },
];

const crumb = { label: 'Clients', to: '/clients' };

/** Tabs with real content; the rest show their "not yet ported" state. */
const PORTED_TABS = new Set(['', 'edit', 'activity', 'onboarding', 'projects']);

function TabBar({ id }: { id: string }) {
  return (
    <nav
      aria-label="Client sections"
      className="mb-4 flex gap-0.5 overflow-x-auto border-b border-line"
    >
      {TABS.map((tab) => (
        <NavLink
          key={tab.slug || 'overview'}
          to={tab.slug ? `/clients/${id}/${tab.slug}` : `/clients/${id}`}
          end
          className={({ isActive }) =>
            cn(
              '-mb-px border-b-2 px-3 py-2 font-medium whitespace-nowrap',
              isActive
                ? 'border-accent text-accent-strong'
                : 'border-transparent text-muted hover:text-fg',
            )
          }
        >
          {tab.label}
        </NavLink>
      ))}
    </nav>
  );
}

function NextAction({ client }: { client: ClientDetail }) {
  const { actor } = useAuth();
  const onboarding = useOnboarding(client.id);
  const projects = useProjects(client.id);
  const data = onboarding.data;
  if (!data) return null;
  if (data.completed_at) {
    if (!projects.data || projects.data.length > 0) return null;
    const canCreate = can(actor?.permissions ?? [], P.projectsCreate);
    return (
      <Alert tone="ok" title="Next required action: Create the delivery project">
        Onboarding is complete and the client is Active.{' '}
        {canCreate ? (
          <Link className="link" to={`/projects/new?client=${client.id}`}>
            Create project →
          </Link>
        ) : (
          'A Project Manager or Account Manager creates the project.'
        )}
      </Alert>
    );
  }
  const next = data.steps.find((s) => s.state !== 'done');
  if (!next) return null;
  return (
    <Alert
      tone={data.status === 'blocked' ? 'bad' : 'info'}
      title={`Next required action: ${next.label}`}
    >
      {next.detail || next.hint}{' '}
      <Link className="link" to={`/clients/${client.id}/onboarding`}>
        Open onboarding →
      </Link>
    </Alert>
  );
}

function TeamPanel({ client }: { client: ClientDetail }) {
  const onboarding = useOnboarding(client.id);
  const team = onboarding.data?.team ?? [];
  return (
    <Panel title="Internal team">
      {team.length ? (
        <ul className="flex flex-col gap-1.5">
          {team.map((member) => (
            <li key={member.id}>{member.full_name}</li>
          ))}
        </ul>
      ) : (
        <EmptyState
          title="No team assigned"
          description="The team is assigned in onboarding step 10."
        />
      )}
    </Panel>
  );
}

function Overview({ client }: { client: ClientDetail }) {
  return (
    <div className="flex flex-col gap-4">
      <NextAction client={client} />
      <div className="grid grid-cols-[repeat(auto-fit,minmax(300px,1fr))] items-start gap-4">
        <Panel title="Profile">
          <KeyValue
            items={[
              ['Legal name', client.name],
              [
                'Website',
                client.website ? (
                  <a
                    className="link"
                    href={
                      client.website.startsWith('http')
                        ? client.website
                        : `https://${client.website}`
                    }
                    target="_blank"
                    rel="noreferrer noopener"
                  >
                    {client.website}
                  </a>
                ) : null,
              ],
              ['Industry', client.industry],
              [
                'Primary contact',
                client.contact_name || client.contact_email ? (
                  <span>
                    {client.contact_name}{' '}
                    {client.contact_email ? (
                      <span className="code">{client.contact_email}</span>
                    ) : null}
                  </span>
                ) : null,
              ],
              ['Account Manager', client.account_manager.full_name],
              ['Created', formatDate(client.created_at)],
            ]}
          />
        </Panel>
        <TeamPanel client={client} />
      </div>
    </div>
  );
}

function ActivityTab({ id }: { id: string }) {
  const activity = useClientActivity(id);
  return (
    <Panel title="Activity timeline">
      {activity.isPending ? <p className="text-muted">Loading…</p> : null}
      {activity.data?.length === 0 ? <EmptyState title="No activity" /> : null}
      {activity.data?.length ? (
        <Timeline
          entries={activity.data.map((entry) => ({
            id: entry.id,
            text: entry.summary,
            meta: `${entry.actor?.full_name ?? 'System'} · ${formatDateTime(entry.occurred_at)}`,
          }))}
        />
      ) : null}
    </Panel>
  );
}

function EditTab({ client }: { client: ClientDetail }) {
  const update = useUpdateClient(client.id);
  const navigate = useNavigate();
  const { toast } = useToast();
  if (!client.can_edit) {
    return (
      <Alert tone="bad" title="Access denied">
        Only this client's Account Manager can edit it.
      </Alert>
    );
  }
  const defaults: ClientFormValues = {
    name: client.name,
    website: client.website ?? '',
    industry: client.industry ?? '',
    contactName: client.contact_name ?? '',
    contactEmail: client.contact_email ?? '',
    accountManagerId: client.account_manager.id,
    confirmDifferentBusiness: false,
  };
  return (
    <Panel title="Edit client">
      <ClientForm
        key={client.updated_at}
        defaultValues={defaults}
        submitLabel="Save changes"
        cancelTo={`/clients/${client.id}`}
        onSubmit={async (values) => {
          await update.mutateAsync(toClientBody(values));
          toast({ title: 'Client updated.' });
          navigate(`/clients/${client.id}`);
        }}
      />
    </Panel>
  );
}

export function Component() {
  const { id = '' } = useParams();
  const location = useLocation();
  const tab = location.pathname.split('/')[3] ?? '';
  const client = useClient(id);

  if (client.isPending) return <PageHeader title="Loading…" crumb={crumb} />;
  if (client.isError || !client.data) {
    const notFound = client.error instanceof ApiError && client.error.status === 404;
    return (
      <>
        <PageHeader title={notFound ? 'Client not found' : 'Something went wrong'} crumb={crumb} />
        <Alert tone="bad">
          {notFound
            ? "This client doesn't exist or you don't have access to it. Employees only see clients they work on."
            : "Couldn't load this client. Reload the page to try again."}
        </Alert>
      </>
    );
  }

  const data = client.data;
  const current = TABS.find((t) => t.slug === tab);
  return (
    <>
      <PageHeader
        crumb={crumb}
        title={
          <span className="flex flex-wrap items-center gap-2">
            {data.name}
            <Badge tone={STATUS_TONE[data.status]}>{data.status_label}</Badge>
          </span>
        }
        description={
          <>
            <span className="code">{data.code}</span>
            {data.domain ? ` · ${data.domain}` : ''} · AM: {data.account_manager.full_name}
          </>
        }
        actions={
          data.can_edit && tab !== 'edit' ? (
            <LinkButton to={`/clients/${data.id}/edit`}>Edit client</LinkButton>
          ) : null
        }
      />
      {tab !== 'edit' ? <TabBar id={data.id} /> : null}
      {tab === '' ? <Overview client={data} /> : null}
      {tab === 'edit' ? <EditTab client={data} /> : null}
      {tab === 'activity' ? <ActivityTab id={data.id} /> : null}
      {tab === 'onboarding' ? <OnboardingTab client={data} /> : null}
      {tab === 'projects' ? <ClientProjectsTab clientId={data.id} /> : null}
      {!PORTED_TABS.has(tab) ? (
        <Panel flush>
          <EmptyState
            title={`${current?.label ?? 'This tab'} isn't ported yet. See PARITY.md`}
            description={<span className="code">frontend/src/features/clients/PARITY.md</span>}
          />
        </Panel>
      ) : null}
    </>
  );
}
