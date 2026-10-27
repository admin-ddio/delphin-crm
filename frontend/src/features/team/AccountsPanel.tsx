/**
 * Team & Roles: every sign-in account with its roles, status and workload. Invite
 * (`users.manage`), change roles (`org.roles.assign`, within your authority) and
 * deactivate / reactivate (`users.manage`). Nobody changes their own account here.
 */
import { Copy, UserPlus } from 'lucide-react';
import { useId, useMemo, useState, type FormEvent } from 'react';

import { Badge, type BadgeTone } from '@/components/ui/Badge';
import { Button, LinkButton } from '@/components/ui/Button';
import { Panel } from '@/components/ui/Card';
import { Dialog } from '@/components/ui/Dialog';
import { EmptyState } from '@/components/ui/EmptyState';
import { SelectField } from '@/components/ui/Fields';
import { Link } from '@/components/ui/Link';
import { useToast } from '@/components/ui/Toast';
import {
  useAccounts,
  useEmployees,
  useInvite,
  useRoles,
  useSetAccountActive,
  useSetUserRoles,
  type Account,
} from '@/features/team/api';
import { ApiError } from '@/lib/api-client';
import { formatDateTime } from '@/lib/format';
import { ROLE_KEYS, ROLE_LABELS, type RoleKey } from '@/lib/permissions';

const STATUS: Record<Account['status'], { label: string; tone: BadgeTone }> = {
  active: { label: 'Active', tone: 'ok' },
  invited: { label: 'Invited', tone: 'info' },
  pending: { label: 'Awaiting approval', tone: 'warn' },
  deactivated: { label: 'Deactivated', tone: 'neutral' },
};

function errorMessage(error: unknown) {
  return error instanceof ApiError ? error.message : 'Something went wrong. Try again.';
}

/** Role options: the server's list when the viewer may read it, else the defaults. */
function useRoleOptions(enabled: boolean) {
  const roles = useRoles(enabled);
  return useMemo(
    () =>
      roles.data?.roles.map((r) => ({ key: r.key, name: r.name, assignable: r.assignable })) ??
      ROLE_KEYS.map((key) => ({ key, name: ROLE_LABELS[key], assignable: key !== 'super_admin' })),
    [roles.data],
  );
}

function InviteDialog({ canReadRoles, onClose }: { canReadRoles: boolean; onClose(): void }) {
  const invite = useInvite();
  const people = useEmployees();
  const roleOptions = useRoleOptions(canReadRoles);
  const { toast } = useToast();
  const ids = { email: useId(), name: useId(), employee: useId() };
  const [email, setEmail] = useState('');
  const [name, setName] = useState('');
  const [roles, setRoles] = useState<string[]>(['employee']);
  const [employee, setEmployee] = useState('');
  const [link, setLink] = useState<string | null>(null);
  const unlinked = (people.data ?? []).filter((p) => !p.user_id);

  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      const result = await invite.mutateAsync({
        email,
        full_name: name,
        roles,
        employee_id: employee || null,
      });
      setLink(result.setup_link);
      toast({ title: `${result.account.full_name} invited.` });
    } catch (error) {
      toast({ title: errorMessage(error), tone: 'error' });
    }
  }

  if (link) {
    return (
      <Dialog open onClose={onClose} title="Invitation ready">
        <div className="flex flex-col gap-3">
          <p className="text-[13px]">
            Send this one-time link to {name}. They set their password with it, then sign in. E-mail
            sending isn't set up yet, so share it yourself.
          </p>
          <input
            className="input font-mono text-xs"
            readOnly
            value={link}
            aria-label="Setup link"
          />
          <div className="flex justify-end gap-2">
            <Button
              onClick={() => {
                void navigator.clipboard?.writeText(link);
                toast({ title: 'Link copied.' });
              }}
            >
              <Copy size={15} /> Copy link
            </Button>
            <Button variant="primary" onClick={onClose}>
              Done
            </Button>
          </div>
        </div>
      </Dialog>
    );
  }

  return (
    <Dialog open onClose={onClose} title="Invite a person">
      <form className="flex flex-col gap-3" onSubmit={submit}>
        <div className="label">
          <label htmlFor={ids.name}>Full name *</label>
          <input
            id={ids.name}
            className="input"
            required
            maxLength={200}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        <div className="label">
          <label htmlFor={ids.email}>Work e-mail *</label>
          <input
            id={ids.email}
            type="email"
            className="input"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <fieldset className="flex flex-col gap-1">
          <legend className="mb-1 text-[13px] font-medium">Roles *</legend>
          {roleOptions.map((r) => (
            <label key={r.key} className="flex items-center gap-2 text-[13px]">
              <input
                type="checkbox"
                disabled={!r.assignable}
                checked={roles.includes(r.key)}
                onChange={(e) =>
                  setRoles((current) =>
                    e.target.checked ? [...current, r.key] : current.filter((k) => k !== r.key),
                  )
                }
              />
              <span className={r.assignable ? undefined : 'text-faint'}>{r.name}</span>
            </label>
          ))}
        </fieldset>
        <div className="label">
          <label htmlFor={ids.employee}>Employee record</label>
          <select
            id={ids.employee}
            className="input"
            value={employee}
            onChange={(e) => setEmployee(e.target.value)}
          >
            <option value="">Don't link</option>
            {unlinked.map((p) => (
              <option key={p.id} value={p.id}>
                {p.full_name} ({p.code})
              </option>
            ))}
          </select>
        </div>
        <div className="flex justify-end gap-2">
          <Button type="button" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" disabled={!roles.length || invite.isPending}>
            Invite
          </Button>
        </div>
      </form>
    </Dialog>
  );
}

function RolesDialog({ account, onClose }: { account: Account; onClose(): void }) {
  const roleOptions = useRoleOptions(true);
  const save = useSetUserRoles();
  const { toast } = useToast();
  const [roles, setRoles] = useState<string[]>(account.roles);
  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      await save.mutateAsync({ userId: account.id, roles });
      toast({ title: `Roles for ${account.full_name} saved.` });
      onClose();
    } catch (error) {
      toast({ title: errorMessage(error), tone: 'error' });
    }
  }
  return (
    <Dialog open onClose={onClose} title={`Roles: ${account.full_name}`}>
      <form className="flex flex-col gap-3" onSubmit={submit}>
        <fieldset className="flex flex-col gap-1">
          <legend className="mb-1 text-[12.5px] text-muted">
            Roles decide what this person can do in the CRM. Their designation doesn't.
          </legend>
          {roleOptions.map((r) => (
            <label key={r.key} className="flex items-center gap-2 text-[13px]">
              <input
                type="checkbox"
                disabled={!r.assignable}
                checked={roles.includes(r.key)}
                onChange={(e) =>
                  setRoles((current) =>
                    e.target.checked ? [...current, r.key] : current.filter((k) => k !== r.key),
                  )
                }
              />
              <span className={r.assignable ? undefined : 'text-faint'}>{r.name}</span>
            </label>
          ))}
        </fieldset>
        <div className="flex justify-end gap-2">
          <Button type="button" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" disabled={!roles.length || save.isPending}>
            Save roles
          </Button>
        </div>
      </form>
    </Dialog>
  );
}

export function AccountsPanel() {
  const accounts = useAccounts();
  const setActive = useSetAccountActive();
  const { toast } = useToast();
  const [role, setRole] = useState('');
  const [status, setStatus] = useState('');
  const [inviting, setInviting] = useState(false);
  const [editing, setEditing] = useState<Account | null>(null);
  const data = accounts.data;
  if (accounts.isError) return null; // no access: the page shows the other panels
  const label = (key: string) => ROLE_LABELS[key as RoleKey] ?? key.replace(/_/g, ' ');
  const rows = (data?.accounts ?? []).filter(
    (a) => (!role || a.roles.includes(role)) && (!status || a.status === status),
  );

  const toggle = async (account: Account) => {
    const active = account.status === 'deactivated';
    if (!active && !window.confirm(`Deactivate ${account.full_name}? They are signed out at once.`))
      return;
    try {
      await setActive.mutateAsync({ id: account.id, active });
      toast({ title: `${account.full_name} ${active ? 'reactivated' : 'deactivated'}.` });
    } catch (error) {
      toast({ title: errorMessage(error), tone: 'error' });
    }
  };

  return (
    <Panel
      title="People & access"
      description="Sign-in accounts, their roles and current workload."
      flush
      actions={
        <div className="flex flex-wrap items-center gap-2">
          <LinkButton size="sm" to="/team/teams?tab=roles">
            Permission matrix →
          </LinkButton>
          {data?.can_invite ? (
            <Button size="sm" variant="primary" onClick={() => setInviting(true)}>
              <UserPlus size={15} /> Invite a person
            </Button>
          ) : null}
        </div>
      }
    >
      <div className="grid gap-3 border-b border-line-soft p-4 sm:grid-cols-[200px_200px]">
        <SelectField
          label="Role"
          placeholder="All roles"
          value={role}
          onChange={(e) => setRole(e.target.value)}
          options={[...new Set((data?.accounts ?? []).flatMap((a) => a.roles))].map((key) => ({
            value: key,
            label: label(key),
          }))}
        />
        <SelectField
          label="Status"
          placeholder="Any status"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          options={Object.entries(STATUS).map(([value, s]) => ({ value, label: s.label }))}
        />
      </div>
      {accounts.isPending ? <EmptyState title="Loading…" /> : null}
      {data && !rows.length ? <EmptyState title="No accounts match" /> : null}
      {rows.length ? (
        <div className="overflow-x-auto">
          <table className="table" data-testid="accounts-table">
            <thead>
              <tr>
                <th>Person</th>
                <th>Roles</th>
                <th>Status</th>
                <th>Open tasks</th>
                <th>Last sign-in</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.map((a) => (
                <tr key={a.id}>
                  <td>
                    {a.employee ? (
                      <Link className="link font-medium" to={`/team/employees/${a.employee.id}`}>
                        {a.full_name}
                      </Link>
                    ) : (
                      <b className="font-medium">{a.full_name}</b>
                    )}
                    {a.is_me ? <span className="text-xs text-muted"> (you)</span> : null}
                    <div className="code">{a.email}</div>
                  </td>
                  <td>
                    <span className="flex flex-wrap gap-1">
                      {a.roles.map((k) => (
                        <Badge key={k} tone="accent">
                          {label(k)}
                        </Badge>
                      ))}
                    </span>
                  </td>
                  <td>
                    <Badge tone={STATUS[a.status].tone}>{STATUS[a.status].label}</Badge>
                  </td>
                  <td className="tabular-nums">
                    {a.open_tasks}
                    {a.overdue_tasks ? (
                      <span className="ml-1 text-xs text-bad">({a.overdue_tasks} overdue)</span>
                    ) : null}
                  </td>
                  <td className="text-[12.5px] text-muted">
                    {a.last_login_at ? formatDateTime(a.last_login_at) : 'Never'}
                  </td>
                  <td className="text-right whitespace-nowrap">
                    {a.editable && data?.can_assign_roles ? (
                      <Button
                        size="sm"
                        onClick={() => setEditing(a)}
                        aria-label={`Change roles for ${a.full_name}`}
                      >
                        Roles
                      </Button>
                    ) : null}{' '}
                    {a.editable && data?.can_deactivate && a.status !== 'pending' ? (
                      <Button
                        size="sm"
                        variant={a.status === 'deactivated' ? 'secondary' : 'danger'}
                        onClick={() => void toggle(a)}
                      >
                        {a.status === 'deactivated' ? 'Reactivate' : 'Deactivate'}
                      </Button>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {inviting ? (
        <InviteDialog
          canReadRoles={Boolean(data?.can_assign_roles)}
          onClose={() => setInviting(false)}
        />
      ) : null}
      {editing ? <RolesDialog account={editing} onClose={() => setEditing(null)} /> : null}
    </Panel>
  );
}
