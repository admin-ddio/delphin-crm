/**
 * Roles & permissions (Organization brief §7–8): the role → permission matrix and who
 * holds which role. The server enforces the authority rules; the UI mirrors them:
 * only permissions you hold can be granted, Super Admin and roles you hold are
 * read-only, you can't change your own roles, and roles above you can't be assigned.
 */
import { Check, Minus } from 'lucide-react';
import { Fragment, useId, useMemo, useState, type FormEvent } from 'react';

import { Alert } from '@/components/ui/Alert';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Panel } from '@/components/ui/Card';
import { Dialog } from '@/components/ui/Dialog';
import { EmptyState } from '@/components/ui/EmptyState';
import { useToast } from '@/components/ui/Toast';
import {
  useRoles,
  useSaveRole,
  useSetUserRoles,
  useUserRoles,
  type RoleOut,
  type RolesOverview,
  type UserRoles,
} from '@/features/team/api';
import { errorMessage } from '@/features/team/org/DepartmentsTab';
import { useAuth } from '@/lib/auth-context';
import { can } from '@/lib/permissions';

function byModule(catalogue: RolesOverview['catalogue']) {
  const groups = new Map<string, RolesOverview['catalogue']>();
  for (const p of catalogue) groups.set(p.module, [...(groups.get(p.module) ?? []), p]);
  return [...groups.entries()];
}

function RoleDialog({
  overview,
  role,
  onClose,
}: {
  overview: RolesOverview;
  role: RoleOut | 'new';
  onClose(): void;
}) {
  const { actor } = useAuth();
  const granted = actor?.permissions ?? [];
  const save = useSaveRole();
  const { toast } = useToast();
  const ids = { key: useId(), name: useId(), description: useId() };
  const existing = role === 'new' ? null : role;
  const [key, setKey] = useState(existing?.key ?? '');
  const [name, setName] = useState(existing?.name ?? '');
  const [description, setDescription] = useState(existing?.description ?? '');
  const [permissions, setPermissions] = useState<string[]>(existing?.permissions ?? []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      await save.mutateAsync({
        create: !existing,
        key,
        name,
        description: description || null,
        permissions,
      });
      toast({ title: existing ? `${name} updated.` : `Role ${name} created.` });
      onClose();
    } catch (error) {
      toast({ title: errorMessage(error), tone: 'error' });
    }
  }

  return (
    <Dialog open onClose={onClose} title={existing ? `Edit ${existing.name}` : 'New role'}>
      <form className="flex flex-col gap-3" onSubmit={submit}>
        {!existing ? (
          <div className="label">
            <label htmlFor={ids.key}>Key *</label>
            <input
              id={ids.key}
              className="input font-mono"
              required
              pattern="[a-z][a-z0-9_]*"
              minLength={2}
              maxLength={64}
              placeholder="seo_lead"
              value={key}
              onChange={(e) => setKey(e.target.value)}
            />
            <span className="text-[12.5px] font-normal text-faint">
              Lowercase letters, digits and underscores. It can't be changed later.
            </span>
          </div>
        ) : null}
        <div className="label">
          <label htmlFor={ids.name}>Name *</label>
          <input
            id={ids.name}
            className="input"
            required
            maxLength={100}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        <div className="label">
          <label htmlFor={ids.description}>Description</label>
          <textarea
            id={ids.description}
            className="input min-h-14"
            maxLength={1000}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </div>
        <div className="flex max-h-80 flex-col gap-3 overflow-y-auto rounded-lg border border-line p-3">
          {byModule(overview.catalogue).map(([module, items]) => (
            <fieldset key={module}>
              <legend className="mb-1 text-[12.5px] font-semibold">{module}</legend>
              {items.map((p) => {
                const holdable = can(granted, p.key);
                return (
                  <label
                    key={p.key}
                    className="flex items-center gap-2 py-0.5 text-[13px]"
                    title={holdable ? p.key : "You can't grant a permission you don't hold"}
                  >
                    <input
                      type="checkbox"
                      disabled={!holdable}
                      checked={permissions.includes(p.key)}
                      onChange={(e) =>
                        setPermissions((current) =>
                          e.target.checked
                            ? [...current, p.key]
                            : current.filter((k) => k !== p.key),
                        )
                      }
                    />
                    <span className={holdable ? undefined : 'text-faint'}>{p.label}</span>
                  </label>
                );
              })}
            </fieldset>
          ))}
        </div>
        <div className="flex justify-end gap-2">
          <Button type="button" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" disabled={save.isPending}>
            Save role
          </Button>
        </div>
      </form>
    </Dialog>
  );
}

function UserRolesDialog({
  overview,
  user,
  onClose,
}: {
  overview: RolesOverview;
  user: UserRoles;
  onClose(): void;
}) {
  const save = useSetUserRoles();
  const { toast } = useToast();
  const [roles, setRoles] = useState<string[]>(user.roles);
  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      await save.mutateAsync({ userId: user.id, roles });
      toast({ title: `Roles for ${user.full_name} saved.` });
      onClose();
    } catch (error) {
      toast({ title: errorMessage(error), tone: 'error' });
    }
  }
  return (
    <Dialog open onClose={onClose} title={`Roles: ${user.full_name}`}>
      <form className="flex flex-col gap-3" onSubmit={submit}>
        <fieldset className="flex flex-col gap-1">
          <legend className="mb-1 text-[12.5px] text-muted">
            Roles decide what this person can do in the CRM. Their designation doesn't.
          </legend>
          {overview.roles.map((r) => (
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
              {!r.assignable ? (
                <span className="text-xs text-faint">(above your authority)</span>
              ) : null}
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

export function RolesTab() {
  const overview = useRoles(true);
  const users = useUserRoles(Boolean(overview.data?.can_assign));
  const [editing, setEditing] = useState<RoleOut | 'new' | null>(null);
  const [assigning, setAssigning] = useState<UserRoles | null>(null);
  const names = useMemo(
    () => new Map((overview.data?.roles ?? []).map((r) => [r.key, r.name])),
    [overview.data],
  );
  if (overview.isPending) return <EmptyState title="Loading…" />;
  if (!overview.data) return <Alert tone="bad">You can't see role settings.</Alert>;
  const data = overview.data;

  return (
    <div className="flex flex-col gap-4">
      <Panel
        title="Permission matrix"
        description="Which role may do what. Read-only columns: Super Admin, roles you hold, and roles with permissions you don't hold."
        flush
        actions={
          data.can_manage ? (
            <Button size="sm" variant="primary" onClick={() => setEditing('new')}>
              New role
            </Button>
          ) : null
        }
      >
        <div className="overflow-x-auto">
          <table className="table text-[12.5px]" data-testid="permission-matrix">
            <thead>
              <tr>
                <th className="sticky left-0 bg-surface">Permission</th>
                {data.roles.map((r) => (
                  <th key={r.key} className="text-center align-bottom">
                    <div className="flex flex-col items-center gap-1">
                      <span className="whitespace-nowrap">{r.name}</span>
                      <span className="text-[11px] font-normal text-muted">
                        {r.member_count} {r.member_count === 1 ? 'person' : 'people'}
                      </span>
                      {data.can_manage && r.editable ? (
                        <Button
                          size="sm"
                          onClick={() => setEditing(r)}
                          aria-label={`Edit ${r.name}`}
                        >
                          Edit
                        </Button>
                      ) : null}
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {byModule(data.catalogue).map(([module, items]) => (
                <Fragment key={module}>
                  <tr>
                    <th
                      colSpan={data.roles.length + 1}
                      className="sticky left-0 bg-sunk text-left text-[12px]"
                      scope="colgroup"
                    >
                      {module}
                    </th>
                  </tr>
                  {items.map((p) => (
                    <tr key={p.key}>
                      <td className="sticky left-0 bg-surface text-left">{p.label}</td>
                      {data.roles.map((r) => {
                        const has = r.permissions.includes('*') || r.permissions.includes(p.key);
                        return (
                          <td key={r.key} className="text-center">
                            {has ? (
                              <Check aria-label="Granted" className="mx-auto size-4 text-ok" />
                            ) : (
                              <Minus
                                aria-label="Not granted"
                                className="mx-auto size-4 text-faint"
                              />
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      {data.can_assign ? (
        <Panel
          title="People and their roles"
          description="Nobody can change their own roles."
          flush
        >
          {users.data?.length ? (
            <div className="overflow-x-auto">
              <table className="table" data-testid="user-roles">
                <thead>
                  <tr>
                    <th>Person</th>
                    <th>E-mail</th>
                    <th>Roles</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {users.data.map((u) => (
                    <tr key={u.id}>
                      <td>{u.employee?.full_name ?? u.full_name}</td>
                      <td className="text-muted">{u.email}</td>
                      <td>
                        <span className="flex flex-wrap gap-1">
                          {u.roles.map((k) => (
                            <Badge key={k} tone="accent">
                              {names.get(k) ?? k}
                            </Badge>
                          ))}
                        </span>
                      </td>
                      <td className="text-right">
                        {u.editable ? (
                          <Button
                            size="sm"
                            onClick={() => setAssigning(u)}
                            aria-label={`Change roles for ${u.full_name}`}
                          >
                            Change roles
                          </Button>
                        ) : (
                          <span className="text-xs text-faint">Read-only</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState title={users.isPending ? 'Loading…' : 'No approved accounts'} />
          )}
        </Panel>
      ) : null}

      {editing ? (
        <RoleDialog
          key={editing === 'new' ? 'new' : editing.key}
          overview={data}
          role={editing}
          onClose={() => setEditing(null)}
        />
      ) : null}
      {assigning ? (
        <UserRolesDialog
          key={assigning.id}
          overview={data}
          user={assigning}
          onClose={() => setAssigning(null)}
        />
      ) : null}
    </div>
  );
}
