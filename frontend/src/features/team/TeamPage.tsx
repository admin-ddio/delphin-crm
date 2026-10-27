/**
 * /team: Team & roles, the people-and-access hub: pending self sign-ups
 * (users.approve) and every sign-in account with roles, status and workload
 * (invite, change roles, deactivate). The permission matrix lives in Organization
 * & Roles (/team/teams?tab=roles) and is linked, not duplicated.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import type { components } from '@/api/schema';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Panel } from '@/components/ui/Card';
import { Dialog } from '@/components/ui/Dialog';
import { EmptyState } from '@/components/ui/EmptyState';
import { PageHeader } from '@/components/ui/PageHeader';
import { AccountsPanel } from '@/features/team/AccountsPanel';
import { useToast } from '@/components/ui/Toast';
import { api, ApiError, unwrap } from '@/lib/api-client';
import { useAuth } from '@/lib/auth-context';
import { formatDateTime } from '@/lib/format';
import { can, P, ROLE_KEYS, ROLE_LABELS, type RoleKey } from '@/lib/permissions';

type Registration = components['schemas']['PendingRegistration'];

export const registrationsKey = ['team', 'registrations'] as const;

function RegistrationRow({ registration }: { registration: Registration }) {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [role, setRole] = useState<RoleKey>('employee');
  const [confirmReject, setConfirmReject] = useState(false);
  const done = () => queryClient.invalidateQueries({ queryKey: registrationsKey });
  const fail = (error: unknown) =>
    toast({
      title: error instanceof ApiError ? error.message : 'Something went wrong.',
      tone: 'error',
    });

  const approve = useMutation({
    mutationFn: async () => {
      const { response, error } = await api.POST('/api/v1/team/registrations/{user_id}/approve', {
        params: { path: { user_id: registration.id } },
        body: { role },
      });
      if (!response.ok) unwrap({ error, response });
    },
    onSuccess: () => {
      toast({ title: `${registration.full_name} approved as ${ROLE_LABELS[role]}.` });
      return done();
    },
    onError: fail,
  });

  const reject = useMutation({
    mutationFn: async () => {
      const { response, error } = await api.POST('/api/v1/team/registrations/{user_id}/reject', {
        params: { path: { user_id: registration.id } },
      });
      if (!response.ok) unwrap({ error, response });
    },
    onSuccess: () => {
      setConfirmReject(false);
      toast({ title: `Sign-up from ${registration.email} rejected.` });
      return done();
    },
    onError: fail,
  });

  const busy = approve.isPending || reject.isPending;
  return (
    <tr data-testid="pending-registration">
      <td>
        <b className="font-medium">{registration.full_name}</b>
        <div className="code">{registration.email}</div>
      </td>
      <td>
        {registration.email_verified ? (
          <Badge tone="ok">Verified</Badge>
        ) : (
          <Badge tone="warn">Not verified yet</Badge>
        )}
      </td>
      <td className="font-mono text-xs text-muted">{formatDateTime(registration.registered_at)}</td>
      <td>
        <div className="flex flex-wrap items-center justify-end gap-2">
          <label className="sr-only" htmlFor={`role-${registration.id}`}>
            Role for {registration.full_name}
          </label>
          <select
            id={`role-${registration.id}`}
            className="input py-1"
            value={role}
            onChange={(event) => setRole(event.target.value as RoleKey)}
          >
            {ROLE_KEYS.map((key) => (
              <option key={key} value={key}>
                {ROLE_LABELS[key]}
              </option>
            ))}
          </select>
          <Button size="sm" variant="primary" disabled={busy} onClick={() => approve.mutate()}>
            Approve
          </Button>
          <Button size="sm" variant="danger" disabled={busy} onClick={() => setConfirmReject(true)}>
            Reject
          </Button>
        </div>
        <Dialog
          open={confirmReject}
          onClose={() => setConfirmReject(false)}
          title="Reject this sign-up?"
          footer={
            <>
              <Button onClick={() => setConfirmReject(false)}>Keep it</Button>
              <Button variant="danger" disabled={busy} onClick={() => reject.mutate()}>
                Reject and delete
              </Button>
            </>
          }
        >
          {registration.full_name} ({registration.email}) will be deleted, including their login.
          They can sign up again later.
        </Dialog>
      </td>
    </tr>
  );
}

function PendingSignUps() {
  const registrations = useQuery({
    queryKey: registrationsKey,
    queryFn: async () => unwrap(await api.GET('/api/v1/team/registrations')),
  });
  const count = registrations.data?.length ?? 0;
  return (
    <Panel
      title="Pending sign-ups"
      description="People who registered themselves. They can't sign in until approved."
      actions={count ? <Badge tone="accent">{count} waiting</Badge> : null}
      flush
    >
      {registrations.isPending ? <EmptyState title="Loading…" /> : null}
      {registrations.isError ? (
        <EmptyState title="Couldn't load sign-ups" description="Reload the page to try again." />
      ) : null}
      {registrations.isSuccess && count === 0 ? (
        <EmptyState title="No one is waiting" description="New sign-ups will appear here." />
      ) : null}
      {count > 0 ? (
        <div className="overflow-x-auto">
          <table className="table">
            <thead>
              <tr>
                <th>Person</th>
                <th>E-mail</th>
                <th>Signed up</th>
                <th className="text-right">Decision</th>
              </tr>
            </thead>
            <tbody>
              {registrations.data?.map((registration) => (
                <RegistrationRow key={registration.id} registration={registration} />
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </Panel>
  );
}

export function Component() {
  const { actor } = useAuth();
  const canApprove = can(actor?.permissions ?? [], P.usersApprove);
  return (
    <>
      <PageHeader
        title="Team & roles"
        description="Who can sign in, with which roles, and how much open work each person has."
      />
      <div className="flex flex-col gap-4">
        {canApprove ? <PendingSignUps /> : null}
        <AccountsPanel />
      </div>
    </>
  );
}
