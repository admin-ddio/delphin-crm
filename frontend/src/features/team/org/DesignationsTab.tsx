/**
 * Designations (job titles), grouped by department. A designation never grants CRM
 * permissions; those come from roles. `org.designations.manage` adds, renames,
 * moves and (de)activates.
 */
import { useId, useMemo, useState } from 'react';

import { Alert } from '@/components/ui/Alert';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Panel } from '@/components/ui/Card';
import { EmptyState } from '@/components/ui/EmptyState';
import { useToast } from '@/components/ui/Toast';
import {
  useDepartments,
  useDesignations,
  useSaveDesignation,
  type Designation,
} from '@/features/team/api';
import { errorMessage } from '@/features/team/org/DepartmentsTab';

export function DesignationsTab({ manage }: { manage: boolean }) {
  const designations = useDesignations();
  const departments = useDepartments();
  const save = useSaveDesignation();
  const { toast } = useToast();
  const ids = { name: useId(), department: useId() };
  const [name, setName] = useState('');
  const [department, setDepartment] = useState('');
  const [renaming, setRenaming] = useState<{ id: string; name: string } | null>(null);

  const groups = useMemo(() => {
    const map = new Map<string, { label: string; items: Designation[] }>();
    map.set('', { label: 'Company-wide', items: [] });
    for (const d of departments.data ?? []) map.set(d.id, { label: d.name, items: [] });
    for (const d of designations.data ?? []) {
      const key = d.department?.id ?? '';
      if (!map.has(key)) map.set(key, { label: d.department?.name ?? 'Company-wide', items: [] });
      map.get(key)?.items.push(d);
    }
    return [...map.entries()].filter(([, g]) => g.items.length);
  }, [designations.data, departments.data]);

  const run = async (body: Parameters<typeof save.mutateAsync>[0], done: string) => {
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
    <div className="flex flex-col gap-4">
      <Alert tone="info">
        Designations are job titles only. Changing someone's designation never changes what they can
        do in the CRM; that comes from their roles.
      </Alert>
      {manage ? (
        <Panel title="Add a designation">
          <form
            className="flex flex-wrap items-end gap-2"
            onSubmit={async (event) => {
              event.preventDefault();
              if (
                await run({ name, department_id: department || null }, `Designation ${name} added.`)
              )
                setName('');
            }}
          >
            <div className="label min-w-56 flex-1">
              <label htmlFor={ids.name}>Title</label>
              <input
                id={ids.name}
                className="input"
                required
                maxLength={100}
                placeholder="Senior SEO Specialist"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
            <div className="label min-w-56">
              <label htmlFor={ids.department}>Department</label>
              <select
                id={ids.department}
                className="input"
                value={department}
                onChange={(e) => setDepartment(e.target.value)}
              >
                <option value="">Company-wide</option>
                {departments.data
                  ?.filter((d) => d.is_active)
                  .map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name}
                    </option>
                  ))}
              </select>
            </div>
            <Button type="submit" variant="primary" disabled={save.isPending}>
              Add designation
            </Button>
          </form>
        </Panel>
      ) : null}
      {designations.isPending ? <EmptyState title="Loading…" /> : null}
      <div className="grid gap-4 xl:grid-cols-2">
        {groups.map(([key, group]) => (
          <Panel key={key || 'company'} title={group.label} flush>
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
                {group.items.map((d) => (
                  <tr key={d.id}>
                    <td>
                      {renaming?.id === d.id ? (
                        <form
                          className="flex gap-1"
                          onSubmit={async (event) => {
                            event.preventDefault();
                            if (
                              await run({ id: d.id, name: renaming.name }, 'Designation renamed.')
                            )
                              setRenaming(null);
                          }}
                        >
                          <input
                            className="input"
                            aria-label={`New name for ${d.name}`}
                            value={renaming.name}
                            maxLength={100}
                            onChange={(e) => setRenaming({ id: d.id, name: e.target.value })}
                          />
                          <Button size="sm" type="submit">
                            Save
                          </Button>
                        </form>
                      ) : (
                        d.name
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
                        <Button
                          size="sm"
                          aria-label={`Rename ${d.name}`}
                          onClick={() => setRenaming({ id: d.id, name: d.name })}
                        >
                          Rename
                        </Button>{' '}
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
          </Panel>
        ))}
      </div>
    </div>
  );
}
