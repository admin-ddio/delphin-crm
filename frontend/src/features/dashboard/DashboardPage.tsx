/**
 * /dashboard. Layout and wording from the clickable demo ("Good day, …", stat
 * tiles, panels). Built from the modules that exist so far (clients, sign-ups);
 * the demo's task, approval, workload and finance tiles arrive with their modules.
 * Every number is counted from the records the signed-in user may see.
 */
import { useQuery } from '@tanstack/react-query';

import { Badge } from '@/components/ui/Badge';
import { LinkButton } from '@/components/ui/Button';
import { Panel, StatCard } from '@/components/ui/Card';
import { EmptyState } from '@/components/ui/EmptyState';
import { Link } from '@/components/ui/Link';
import { PageHeader } from '@/components/ui/PageHeader';
import { useClients, type ClientStatus } from '@/features/clients/api';
import { STATUS_TONE } from '@/features/clients/ClientsListPage';
import { useOnboardingBoard } from '@/features/onboarding/api';
import { ONBOARDING_STATUS } from '@/features/onboarding/OnboardingTab';
import { registrationsKey } from '@/features/team/TeamPage';
import { Progress } from '@/components/ui/Data';
import { api, unwrap } from '@/lib/api-client';
import { useAuth } from '@/lib/auth-context';
import { formatDate } from '@/lib/format';
import { can, P, ROLE_LABELS, type RoleKey } from '@/lib/permissions';

function useClientCount(status?: ClientStatus) {
  const result = useClients({ status, page_size: 1 });
  return result.data?.total;
}

function ClientTiles() {
  const total = useClientCount();
  const pending = useClientCount('contract_pending');
  const onboarding = useClientCount('onboarding');
  const active = useClientCount('active');
  const show = (n: number | undefined) => (n === undefined ? '…' : n);
  return (
    <div className="mb-4 grid grid-cols-[repeat(auto-fit,minmax(150px,1fr))] gap-4" data-testid="dashboard-tiles">
      <StatCard label="Clients" value={show(total)} hint="All clients you can see" />
      <StatCard label="Contract pending" value={show(pending)} />
      <StatCard label="In onboarding" value={show(onboarding)} />
      <StatCard label="Active clients" value={show(active)} hint="Onboarding completed" />
    </div>
  );
}

function RecentClients({ canCreate }: { canCreate: boolean }) {
  const recent = useClients({ sort: '-created_at', page_size: 5 });
  return (
    <Panel
      title="Recently added clients"
      flush
      actions={
        <Link className="link text-[13px]" to="/clients">
          All clients →
        </Link>
      }
    >
      {recent.isPending ? <EmptyState title="Loading…" /> : null}
      {recent.data?.total === 0 ? (
        <EmptyState
          title="No clients yet"
          description="Create the first client once the contract is signed."
          action={
            canCreate ? (
              <LinkButton to="/clients/new" variant="primary" size="sm">
                New client
              </LinkButton>
            ) : null
          }
        />
      ) : null}
      {recent.data?.items.length ? (
        <div className="overflow-x-auto">
          <table className="table">
            <thead>
              <tr>
                <th>Client</th>
                <th>Status</th>
                <th>Added</th>
              </tr>
            </thead>
            <tbody>
              {recent.data.items.map((client) => (
                <tr key={client.id}>
                  <td>
                    <Link className="link" to={`/clients/${client.id}`}>
                      {client.name}
                    </Link>
                    <div className="code">{client.code}</div>
                  </td>
                  <td>
                    <Badge tone={STATUS_TONE[client.status]}>{client.status_label}</Badge>
                  </td>
                  <td className="font-mono text-xs tabular-nums">{formatDate(client.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </Panel>
  );
}

function OnboardingPipeline() {
  const board = useOnboardingBoard();
  const open = board.data?.filter((row) => row.status !== 'completed') ?? [];
  return (
    <Panel
      title="Onboarding pipeline"
      flush
      actions={
        <Link className="link text-[13px]" to="/onboarding">
          All onboarding →
        </Link>
      }
    >
      {board.isPending ? <EmptyState title="Loading…" /> : null}
      {board.data && open.length === 0 ? <EmptyState title="No clients in onboarding" /> : null}
      {open.length ? (
        <div className="overflow-x-auto">
          <table className="table" data-testid="onboarding-pipeline">
            <thead>
              <tr>
                <th>Client</th>
                <th>Progress</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {open.slice(0, 8).map((row) => {
                const status = ONBOARDING_STATUS[row.status];
                return (
                  <tr key={row.client_id}>
                    <td>
                      <Link className="link" to={`/clients/${row.client_id}/onboarding`}>
                        {row.client_name}
                      </Link>
                      {row.current_step ? <div className="code">{row.current_step}</div> : null}
                    </td>
                    <td className="w-[40%]">
                      <Progress value={row.progress} label={`${row.client_name} onboarding progress`} />
                    </td>
                    <td>
                      <Badge tone={status.tone}>{status.label}</Badge>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}
    </Panel>
  );
}

function PendingSignUpsCount() {
  const registrations = useQuery({
    queryKey: registrationsKey,
    queryFn: async () => unwrap(await api.GET('/api/v1/team/registrations')),
  });
  const count = registrations.data?.length ?? 0;
  return (
    <Link className="link" to="/team">
      Review sign-ups {count ? <Badge tone="accent">{count} waiting</Badge> : null}
    </Link>
  );
}

export function Component() {
  const { actor } = useAuth();
  if (!actor) return null;
  const permissions = actor.permissions;
  const canSeeClients = can(permissions, P.clientsViewAll) || can(permissions, P.clientsCreate);
  const canCreate = can(permissions, P.clientsCreate);
  const canApprove = can(permissions, P.usersApprove);
  const role = ROLE_LABELS[actor.roles[0] as RoleKey] ?? actor.roles[0] ?? 'no role';
  const firstName = actor.fullName.split(' ')[0];

  return (
    <>
      <PageHeader
        title={`Good day, ${firstName}`}
        description={
          <>
            You're signed in as <b className="text-fg">{role}</b>. Every number is counted from the
            records you can see.
          </>
        }
        actions={
          canCreate ? (
            <LinkButton to="/clients/new" variant="primary">
              New client
            </LinkButton>
          ) : null
        }
      />

      {canSeeClients ? <ClientTiles /> : null}

      <div className="grid grid-cols-[repeat(auto-fit,minmax(300px,1fr))] items-start gap-4">
        {canSeeClients ? <OnboardingPipeline /> : null}
        {canSeeClients ? <RecentClients canCreate={canCreate} /> : null}
        <Panel title="Quick actions">
          <ul className="flex flex-col gap-2 text-[13px]">
            {canCreate ? (
              <li>
                <Link className="link" to="/clients/new">
                  Create a client
                </Link>
              </li>
            ) : null}
            {canSeeClients ? (
              <li>
                <Link className="link" to="/clients">
                  Browse CRM &amp; Clients
                </Link>
              </li>
            ) : null}
            {canApprove ? (
              <li>
                <PendingSignUpsCount />
              </li>
            ) : null}
            <li>
              <Link className="link" to="/account">
                My account &amp; password
              </Link>
            </li>
          </ul>
        </Panel>
        <Panel title="Coming next">
          <EmptyState
            title="More of the dashboard arrives with each module"
            description="Open tasks, overdue work, approvals, onboarding pipeline, team workload and finance tiles appear as those modules are ported."
          />
        </Panel>
      </div>
    </>
  );
}
