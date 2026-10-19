/**
 * /team/teams: departments (heads, headcount), designations, and the organisation
 * chart built from direct reporting lines. HR (`hr.manage`) edits; everyone views.
 */
import { ChevronDown, ChevronRight } from 'lucide-react';
import { useId, useMemo, useState, type FormEvent } from 'react';

import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Panel } from '@/components/ui/Card';
import { Tabs } from '@/components/ui/Data';
import { Dialog } from '@/components/ui/Dialog';
import { EmptyState } from '@/components/ui/EmptyState';
import { Link } from '@/components/ui/Link';
import { PageHeader } from '@/components/ui/PageHeader';
import { useToast } from '@/components/ui/Toast';
import {
  useDepartments,
  useDesignations,
  useEmployees,
  useSaveDepartment,
  useSaveDesignation,
  type Department,
  type EmployeeListItem,
} from '@/features/team/api';
import { ApiError } from '@/lib/api-client';
import { useAuth } from '@/lib/auth-context';
import { can, P } from '@/lib/permissions';

type View = 'departments' | 'chart' | 'designations';

function errorMessage(error: unknown) {
  return error instanceof ApiError ? error.message : 'Something went wrong. Try again.';
}

function DepartmentDialog({
  department,
  onClose,
}: {
  department: Department | 'new' | null;
  onClose(): void;
}) {
  const save = useSaveDepartment();
  const people = useEmployees();
  const { toast } = useToast();
  const ids = { name: useId(), description: useId(), head: useId() };
  const existing = department && department !== 'new' ? department : null;
  const [name, setName] = useState(existing?.name ?? '');
  const [description, setDescription] = useState(existing?.description ?? '');
  const [head, setHead] = useState(existing?.head?.id ?? '');

  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      await save.mutateAsync({
        id: existing?.id,
        name,
        description: description || null,
        head_id: head || null,
      });
      toast({ title: existing ? 'Department updated.' : `Department ${name} created.` });
      onClose();
    } catch (error) {
      toast({ title: errorMessage(error), tone: 'error' });
    }
  }

  return (
    <Dialog
      open={department !== null}
      onClose={onClose}
      title={existing ? `Edit ${existing.name}` : 'New department'}
    >
      <form className="flex flex-col gap-3" onSubmit={submit}>
        <div className="label">
          <label htmlFor={ids.name}>Name</label>
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
            className="input min-h-16"
            maxLength={1000}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </div>
        <div className="label">
          <label htmlFor={ids.head}>Department head</label>
          <select
            id={ids.head}
            className="input"
            value={head}
            onChange={(e) => setHead(e.target.value)}
          >
            <option value="">To be assigned</option>
            {people.data?.map((p) => (
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
          <Button type="submit" variant="primary" disabled={save.isPending}>
            Save
          </Button>
        </div>
      </form>
    </Dialog>
  );
}

function Departments({ manage }: { manage: boolean }) {
  const departments = useDepartments();
  const save = useSaveDepartment();
  const { toast } = useToast();
  const [editing, setEditing] = useState<Department | 'new' | null>(null);
  const toggle = async (d: Department) => {
    try {
      await save.mutateAsync({ id: d.id, is_active: !d.is_active });
      toast({ title: `${d.name} ${d.is_active ? 'deactivated' : 'reactivated'}.` });
    } catch (error) {
      toast({ title: errorMessage(error), tone: 'error' });
    }
  };
  return (
    <Panel
      flush
      title="Departments"
      actions={
        manage ? (
          <Button size="sm" variant="primary" onClick={() => setEditing('new')}>
            New department
          </Button>
        ) : null
      }
    >
      {departments.isPending ? <EmptyState title="Loading…" /> : null}
      {departments.data?.length ? (
        <div className="overflow-x-auto">
          <table className="table" data-testid="departments-table">
            <thead>
              <tr>
                <th>Department</th>
                <th>Head</th>
                <th>Headcount</th>
                <th>Status</th>
                {manage ? <th /> : null}
              </tr>
            </thead>
            <tbody>
              {departments.data.map((d) => (
                <tr key={d.id}>
                  <td>
                    <Link className="link" to={`/team/employees?department=${d.id}`}>
                      {d.name}
                    </Link>
                    {d.description ? (
                      <div className="text-xs text-muted">{d.description}</div>
                    ) : null}
                  </td>
                  <td>
                    {d.head ? (
                      <Link className="link" to={`/team/employees/${d.head.id}`}>
                        {d.head.full_name}
                      </Link>
                    ) : (
                      <span className="text-muted">To be assigned</span>
                    )}
                  </td>
                  <td className="font-mono text-xs tabular-nums">{d.headcount}</td>
                  <td>
                    <Badge tone={d.is_active ? 'ok' : 'neutral'}>
                      {d.is_active ? 'Active' : 'Inactive'}
                    </Badge>
                  </td>
                  {manage ? (
                    <td className="text-right whitespace-nowrap">
                      <Button size="sm" onClick={() => setEditing(d)} aria-label={`Edit ${d.name}`}>
                        Edit
                      </Button>{' '}
                      <Button size="sm" onClick={() => void toggle(d)}>
                        {d.is_active ? 'Deactivate' : 'Reactivate'}
                      </Button>
                    </td>
                  ) : null}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {editing ? (
        <DepartmentDialog
          key={editing === 'new' ? 'new' : editing.id}
          department={editing}
          onClose={() => setEditing(null)}
        />
      ) : null}
    </Panel>
  );
}

function Designations({ manage }: { manage: boolean }) {
  const designations = useDesignations();
  const save = useSaveDesignation();
  const { toast } = useToast();
  const id = useId();
  const [name, setName] = useState('');
  const run = async (body: { id?: string; name?: string; is_active?: boolean }, done: string) => {
    try {
      await save.mutateAsync(body);
      toast({ title: done });
      return true;
    } catch (error) {
      toast({ title: errorMessage(error), tone: 'error' });
      return false;
    }
  };
  return (
    <Panel title="Designations" flush>
      {designations.data?.length ? (
        <div className="overflow-x-auto">
          <table className="table">
            <thead>
              <tr>
                <th>Designation</th>
                <th>People</th>
                <th>Status</th>
                {manage ? <th /> : null}
              </tr>
            </thead>
            <tbody>
              {designations.data.map((d) => (
                <tr key={d.id}>
                  <td>{d.name}</td>
                  <td className="font-mono text-xs tabular-nums">{d.headcount}</td>
                  <td>
                    <Badge tone={d.is_active ? 'ok' : 'neutral'}>
                      {d.is_active ? 'Active' : 'Inactive'}
                    </Badge>
                  </td>
                  {manage ? (
                    <td className="text-right">
                      <Button
                        size="sm"
                        onClick={() =>
                          void run(
                            { id: d.id, is_active: !d.is_active },
                            `${d.name} ${d.is_active ? 'deactivated' : 'reactivated'}.`,
                          )
                        }
                      >
                        {d.is_active ? 'Deactivate' : 'Reactivate'}
                      </Button>
                    </td>
                  ) : null}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <EmptyState title="No designations" />
      )}
      {manage ? (
        <form
          className="flex items-end gap-2 border-t border-line-soft p-3.5"
          onSubmit={async (event) => {
            event.preventDefault();
            if (await run({ name }, `Designation ${name} added.`)) setName('');
          }}
        >
          <div className="label flex-1">
            <label htmlFor={id}>New designation</label>
            <input
              id={id}
              className="input"
              required
              maxLength={100}
              placeholder="SEO Specialist"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <Button type="submit" size="sm" disabled={save.isPending}>
            Add designation
          </Button>
        </form>
      ) : null}
    </Panel>
  );
}

function Node({
  employee,
  childrenOf,
  depth,
}: {
  employee: EmployeeListItem;
  childrenOf: Map<string, EmployeeListItem[]>;
  depth: number;
}) {
  const kids = childrenOf.get(employee.id) ?? [];
  const [open, setOpen] = useState(depth < 2);
  return (
    <li>
      <div className="flex items-center gap-1.5 py-1">
        {kids.length ? (
          <button
            type="button"
            className="cursor-pointer rounded p-0.5 text-muted hover:bg-sunk"
            aria-label={`${open ? 'Collapse' : 'Expand'} ${employee.full_name}'s team`}
            aria-expanded={open}
            onClick={() => setOpen(!open)}
          >
            {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          </button>
        ) : (
          <span className="inline-block w-[18px]" />
        )}
        <Link className="link font-medium" to={`/team/employees/${employee.id}`}>
          {employee.full_name}
        </Link>
        <span className="text-[12.5px] text-muted">
          {[employee.designation?.name, employee.department?.name].filter(Boolean).join(' · ')}
        </span>
        {kids.length ? <span className="code">{kids.length}</span> : null}
      </div>
      {open && kids.length ? (
        <ul className="ml-[9px] border-l border-line pl-4">
          {kids.map((kid) => (
            <Node key={kid.id} employee={kid} childrenOf={childrenOf} depth={depth + 1} />
          ))}
        </ul>
      ) : null}
    </li>
  );
}

function OrgChart() {
  const employees = useEmployees();
  const { roots, childrenOf } = useMemo(() => {
    const list = employees.data ?? [];
    const ids = new Set(list.map((e) => e.id));
    const map = new Map<string, EmployeeListItem[]>();
    const top: EmployeeListItem[] = [];
    for (const e of list) {
      if (e.manager && ids.has(e.manager.id)) {
        map.set(e.manager.id, [...(map.get(e.manager.id) ?? []), e]);
      } else {
        top.push(e);
      }
    }
    return { roots: top, childrenOf: map };
  }, [employees.data]);
  return (
    <Panel
      title="Organisation chart"
      description="Direct reporting lines. People without a manager appear at the top level."
    >
      {employees.isPending ? <p className="text-muted">Loading…</p> : null}
      {employees.data?.length === 0 ? <EmptyState title="No employees yet" /> : null}
      <ul data-testid="org-chart">
        {roots.map((e) => (
          <Node key={e.id} employee={e} childrenOf={childrenOf} depth={0} />
        ))}
      </ul>
    </Panel>
  );
}

export function Component() {
  const { actor } = useAuth();
  const manage = can(actor?.permissions ?? [], P.hrManage);
  const [view, setView] = useState<View>('departments');
  return (
    <>
      <PageHeader
        title="Departments & org chart"
        description="Departments, their heads and headcount, and who reports to whom. Department heads, managers and leave approvers are configured here and on each profile."
      />
      <Tabs
        label="Organisation views"
        value={view}
        onChange={(key) => setView(key as View)}
        items={[
          { key: 'departments', label: 'Departments' },
          { key: 'chart', label: 'Org chart' },
          { key: 'designations', label: 'Designations' },
        ]}
      />
      {view === 'departments' ? <Departments manage={manage} /> : null}
      {view === 'chart' ? <OrgChart /> : null}
      {view === 'designations' ? <Designations manage={manage} /> : null}
    </>
  );
}
