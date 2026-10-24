/**
 * Departments: purpose, executive owner(s) (= default functional managers), head,
 * default Project Manager and headcount. `org.departments.manage` creates, edits,
 * renames, deactivates and reactivates; everyone with `org.view` reads.
 */
import { useId, useState, type FormEvent } from 'react';

import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Panel } from '@/components/ui/Card';
import { Dialog } from '@/components/ui/Dialog';
import { EmptyState } from '@/components/ui/EmptyState';
import { Link } from '@/components/ui/Link';
import { useToast } from '@/components/ui/Toast';
import {
  useDepartments,
  useEmployees,
  useSaveDepartment,
  type Department,
} from '@/features/team/api';
import { LineSample } from '@/features/team/org/Relations';
import { ApiError } from '@/lib/api-client';

export function errorMessage(error: unknown) {
  return error instanceof ApiError ? error.message : 'Something went wrong. Try again.';
}

function DepartmentDialog({
  department,
  onClose,
}: {
  department: Department | 'new';
  onClose(): void;
}) {
  const save = useSaveDepartment();
  const people = useEmployees();
  const { toast } = useToast();
  const ids = {
    name: useId(),
    description: useId(),
    head: useId(),
    delivery: useId(),
    owners: useId(),
  };
  const existing = department !== 'new' ? department : null;
  const [name, setName] = useState(existing?.name ?? '');
  const [description, setDescription] = useState(existing?.description ?? '');
  const [head, setHead] = useState(existing?.head?.id ?? '');
  const [delivery, setDelivery] = useState(existing?.delivery_manager?.id ?? '');
  const [owners, setOwners] = useState<string[]>(existing?.owners.map((o) => o.id) ?? []);
  const options = people.data ?? [];

  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      await save.mutateAsync({
        id: existing?.id,
        name,
        description: description || null,
        head_id: head || null,
        delivery_manager_id: delivery || null,
        owner_ids: owners,
      });
      toast({ title: existing ? `${name} updated.` : `Department ${name} created.` });
      onClose();
    } catch (error) {
      toast({ title: errorMessage(error), tone: 'error' });
    }
  }

  const personSelect = (id: string, value: string, onChange: (v: string) => void) => (
    <select id={id} className="input" value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="">Unassigned</option>
      {options.map((p) => (
        <option key={p.id} value={p.id}>
          {p.full_name} ({p.code})
        </option>
      ))}
    </select>
  );

  return (
    <Dialog open onClose={onClose} title={existing ? `Edit ${existing.name}` : 'New department'}>
      <form className="flex flex-col gap-3" onSubmit={submit}>
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
          <label htmlFor={ids.description}>Purpose</label>
          <textarea
            id={ids.description}
            className="input min-h-16"
            maxLength={1000}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </div>
        <fieldset className="label">
          <legend id={ids.owners} className="mb-1 flex items-center gap-1.5">
            <LineSample kind="functional_manager" /> Executive owner(s): functional reporting
          </legend>
          <div
            className="flex max-h-40 flex-col gap-1 overflow-y-auto rounded-lg border border-line p-2 font-normal"
            role="group"
            aria-labelledby={ids.owners}
          >
            {options.map((p) => (
              <label key={p.id} className="flex items-center gap-2 text-[13px]">
                <input
                  type="checkbox"
                  checked={owners.includes(p.id)}
                  onChange={(e) =>
                    setOwners((current) =>
                      e.target.checked ? [...current, p.id] : current.filter((i) => i !== p.id),
                    )
                  }
                />
                {p.full_name}
                <span className="text-muted">{p.designation?.name}</span>
              </label>
            ))}
          </div>
          <span className="text-[12.5px] font-normal text-faint">
            Members report functionally to these people unless set otherwise on the employee.
          </span>
        </fieldset>
        <div className="label">
          <label htmlFor={ids.head}>Department head</label>
          {personSelect(ids.head, head, setHead)}
        </div>
        <div className="label">
          <label htmlFor={ids.delivery}>Default Project Manager (delivery)</label>
          {personSelect(ids.delivery, delivery, setDelivery)}
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

export function DepartmentsTab({ manage }: { manage: boolean }) {
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
  const unassigned = <span className="text-muted">Unassigned</span>;
  return (
    <Panel
      flush
      title="Departments"
      description="Executive owners give functional reporting; the default Project Manager gives delivery reporting."
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
                <th>Executive owner(s)</th>
                <th>Head</th>
                <th>Default PM</th>
                <th>People</th>
                <th>Status</th>
                {manage ? <th /> : null}
              </tr>
            </thead>
            <tbody>
              {departments.data.map((d) => (
                <tr key={d.id}>
                  <td className="max-w-80">
                    <Link className="link font-medium" to={`/team/employees?department=${d.id}`}>
                      {d.name}
                    </Link>
                    {d.description ? (
                      <div className="text-xs text-muted">{d.description}</div>
                    ) : null}
                  </td>
                  <td>
                    {d.owners.length ? d.owners.map((o) => o.full_name).join(' & ') : unassigned}
                  </td>
                  <td>{d.head?.full_name ?? unassigned}</td>
                  <td>{d.delivery_manager?.full_name ?? unassigned}</td>
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
