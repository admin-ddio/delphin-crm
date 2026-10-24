/**
 * /clients/:id and its tabs (/clients/:id/<tab>), from the product mockups: header
 * with logo, name, status and meta line, an Actions menu, and the onboarding tabs
 * Overview · Questionnaire · Access · KPIs · Meetings · Team · Documents ·
 * Projects · Activity · Summary. The tab comes from the URL.
 */
import {
  Activity,
  ChevronDown,
  ClipboardList,
  FileText,
  FolderKanban,
  Globe,
  LayoutDashboard,
  ListChecks,
  Lock,
  MoreVertical,
  Target,
  CalendarDays,
  Users,
  type LucideIcon,
} from 'lucide-react';
import { useState } from 'react';
import { NavLink, useLocation, useNavigate, useParams } from 'react-router';

import { Alert } from '@/components/ui/Alert';
import { Avatar } from '@/components/ui/Avatar';
import { Badge } from '@/components/ui/Badge';
import { Button, LinkButton } from '@/components/ui/Button';
import { Panel } from '@/components/ui/Card';
import { Timeline } from '@/components/ui/Data';
import { EmptyState } from '@/components/ui/EmptyState';
import { Menu } from '@/components/ui/Menu';
import { PageHeader } from '@/components/ui/PageHeader';
import { useToast } from '@/components/ui/Toast';
import {
  BUSINESS_TYPES,
  labelOf,
  STATUS_TONE,
  useChangeClientStatus,
  useClient,
  useClientActivity,
  useUpdateClient,
  type ClientDetail,
} from '@/features/clients/api';
import { ClientForm, fromClient, toClientBody } from '@/features/clients/ClientForm';
import { DocumentsTab } from '@/features/documents/DocumentsTab';
import { MeetingsTab } from '@/features/meetings/MeetingsTab';
import { useOnboarding } from '@/features/onboarding/api';
import { AccessTab } from '@/features/onboarding/AccessTab';
import { KpisTab } from '@/features/onboarding/KpisTab';
import { OverviewTab } from '@/features/onboarding/OverviewTab';
import { QuestionnaireLinkDialog } from '@/features/onboarding/QuestionnaireLinkDialog';
import { QuestionnaireTab } from '@/features/onboarding/QuestionnaireTab';
import { SummaryTab } from '@/features/onboarding/SummaryTab';
import { TeamTab } from '@/features/onboarding/TeamTab';
import { ClientProjectsTab } from '@/features/projects/ClientProjectsTab';
import { ApiError } from '@/lib/api-client';
import { useAuth } from '@/lib/auth-context';
import { countryName, flag } from '@/lib/countries';
import { formatDateTime } from '@/lib/format';
import { can, P } from '@/lib/permissions';
import { cn } from '@/lib/utils';

const TABS: { slug: string; label: string; icon: LucideIcon }[] = [
  { slug: '', label: 'Overview', icon: LayoutDashboard },
  { slug: 'questionnaire', label: 'Questionnaire', icon: ClipboardList },
  { slug: 'access', label: 'Access', icon: Lock },
  { slug: 'kpis', label: 'KPIs', icon: Target },
  { slug: 'meetings', label: 'Meetings', icon: CalendarDays },
  { slug: 'team', label: 'Team', icon: Users },
  { slug: 'documents', label: 'Documents', icon: FileText },
  { slug: 'projects', label: 'Projects', icon: FolderKanban },
  { slug: 'activity', label: 'Activity', icon: Activity },
  { slug: 'summary', label: 'Summary', icon: ListChecks },
];
/** Earlier links (e.g. /clients/:id/onboarding) land on the summary. */
const ALIASES: Record<string, string> = { onboarding: 'summary' };

const crumb = { label: 'Clients', to: '/clients' };

function TabBar({ id }: { id: string }) {
  return (
    <nav
      aria-label="Client sections"
      className="mb-6 flex gap-1 overflow-x-auto border-b border-line"
    >
      {TABS.map(({ slug, label, icon: Icon }) => (
        <NavLink
          key={slug || 'overview'}
          to={slug ? `/clients/${id}/${slug}` : `/clients/${id}`}
          end
          className={({ isActive }) =>
            cn(
              '-mb-px inline-flex items-center gap-2 border-b-2 px-4 py-3 text-sm font-medium whitespace-nowrap',
              isActive
                ? 'border-accent text-accent'
                : 'border-transparent text-muted hover:text-fg',
            )
          }
        >
          <Icon aria-hidden className="size-4" />
          {label}
        </NavLink>
      ))}
    </nav>
  );
}

function ActivityTab({ id }: { id: string }) {
  const activity = useClientActivity(id);
  return (
    <Panel title="Activity Timeline" icon={Activity}>
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
  const [busy, setBusy] = useState(false);
  if (!client.can_edit) {
    return (
      <Alert tone="bad" title="Access denied">
        Only this client's Account Manager can edit it.
      </Alert>
    );
  }
  return (
    <div className="flex flex-col gap-4">
      <ClientForm
        key={client.updated_at}
        formId="client-edit-form"
        defaultValues={fromClient(client)}
        onBusyChange={setBusy}
        onSubmit={async (values) => {
          await update.mutateAsync(toClientBody(values));
          toast({ title: 'Client updated.' });
          navigate(`/clients/${client.id}`);
        }}
      />
      <div className="flex gap-3">
        <Button type="submit" form="client-edit-form" variant="primary" disabled={busy}>
          {busy ? 'Saving…' : 'Save changes'}
        </Button>
        <LinkButton to={`/clients/${client.id}`}>Cancel</LinkButton>
      </div>
    </div>
  );
}

function HeaderActions({ client }: { client: ClientDetail }) {
  const { actor } = useAuth();
  const onboarding = useOnboarding(client.id);
  const change = useChangeClientStatus(client.id);
  const { toast } = useToast();
  const [linkOpen, setLinkOpen] = useState(false);
  const detail = onboarding.data;
  const manage = detail?.permissions.manage ?? false;
  const run = async (action: 'hold' | 'complete' | 'reactivate', done: string) => {
    try {
      await change.mutateAsync(action);
      toast({ title: done });
    } catch (error) {
      toast({
        title: error instanceof ApiError ? error.message : 'Something went wrong. Try again.',
        tone: 'error',
      });
    }
  };
  return (
    <>
      <Menu
        label="Client actions"
        trigger={
          <span className="inline-flex items-center gap-2 rounded-lg bg-accent px-4 py-2.5 text-sm font-medium text-on-accent shadow-sm hover:bg-accent-strong">
            <MoreVertical aria-hidden className="size-4" />
            Actions
            <ChevronDown aria-hidden className="size-4" />
          </span>
        }
        items={[
          { label: 'Edit client', to: `/clients/${client.id}/edit`, hidden: !client.can_edit },
          {
            label: 'Send questionnaire link',
            hidden: !manage || detail?.questionnaire.status === 'submitted',
            onSelect: () => setLinkOpen(true),
          },
          {
            label: 'Schedule meeting',
            to: `/clients/${client.id}/meetings?new=1`,
            hidden: !detail?.permissions.schedule_meetings,
          },
          {
            label: 'Create project',
            to: `/projects/new?client=${client.id}`,
            hidden: !detail?.completed_at || !can(actor?.permissions ?? [], P.projectsCreate),
          },
          { label: 'Onboarding summary', to: `/clients/${client.id}/summary` },
          {
            label: 'Put on hold',
            hidden: !client.can_edit || !['onboarding', 'active'].includes(client.status),
            onSelect: () => void run('hold', `${client.name} is on hold.`),
          },
          {
            label: 'Mark completed',
            hidden: !client.can_edit || client.status !== 'active',
            onSelect: () => void run('complete', `${client.name} marked completed.`),
          },
          {
            label: 'Reactivate',
            hidden: !client.can_edit || !['on_hold', 'completed'].includes(client.status),
            onSelect: () => void run('reactivate', `${client.name} reactivated.`),
          },
        ]}
      />
      <QuestionnaireLinkDialog
        clientId={client.id}
        open={linkOpen}
        onClose={() => setLinkOpen(false)}
      />
    </>
  );
}

export function Component() {
  const { id = '' } = useParams();
  const location = useLocation();
  const raw = location.pathname.split('/')[3] ?? '';
  const tab = ALIASES[raw] ?? raw;
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
  const known = tab === 'edit' || TABS.some((t) => t.slug === tab);
  const meta = [
    data.website ? (
      <span key="w" className="inline-flex items-center gap-1.5">
        <Globe aria-hidden className="size-4" />
        {data.website}
      </span>
    ) : null,
    data.industry,
    data.country ? `${flag(data.country)} ${countryName(data.country)}` : null,
    labelOf(BUSINESS_TYPES, data.business_type),
  ].filter(Boolean);

  return (
    <>
      <PageHeader
        crumb={crumb}
        leading={<Avatar name={data.name} size="lg" />}
        title={
          <span className="flex flex-wrap items-center gap-3">
            {data.name}
            <Badge tone={STATUS_TONE[data.status]}>{data.status_label}</Badge>
          </span>
        }
        description={
          <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
            {meta.map((item, i) => (
              <span key={i} className="inline-flex items-center gap-3">
                {i ? (
                  <span aria-hidden className="text-faint">
                    ·
                  </span>
                ) : null}
                {item}
              </span>
            ))}
            <span aria-hidden className="text-faint">
              ·
            </span>
            <span className="code">{data.code}</span>
          </span>
        }
        actions={tab !== 'edit' ? <HeaderActions client={data} /> : null}
      />
      {tab !== 'edit' ? <TabBar id={data.id} /> : null}
      {tab === '' ? <OverviewTab client={data} /> : null}
      {tab === 'edit' ? <EditTab client={data} /> : null}
      {tab === 'questionnaire' ? <QuestionnaireTab client={data} /> : null}
      {tab === 'access' ? <AccessTab clientId={data.id} /> : null}
      {tab === 'kpis' ? <KpisTab clientId={data.id} /> : null}
      {tab === 'meetings' ? <MeetingsTab client={data} /> : null}
      {tab === 'team' ? <TeamTab clientId={data.id} /> : null}
      {tab === 'documents' ? <DocumentsTab clientId={data.id} /> : null}
      {tab === 'projects' ? <ClientProjectsTab clientId={data.id} /> : null}
      {tab === 'activity' ? <ActivityTab id={data.id} /> : null}
      {tab === 'summary' ? <SummaryTab client={data} /> : null}
      {!known ? (
        <Panel flush>
          <EmptyState
            title="This section isn't available yet"
            description="Contacts, services, billing and communications arrive with their modules."
          />
        </Panel>
      ) : null}
    </>
  );
}
