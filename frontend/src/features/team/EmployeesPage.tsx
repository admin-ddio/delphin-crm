/**
 * /team/employees: the employee directory (everyone signed in). Search, department
 * and status filters live in the URL. Layout follows the CRM's list pages.
 */
import { useEffect, useId, useState } from 'react';
import { useSearchParams } from 'react-router';

import { Badge } from '@/components/ui/Badge';
import { LinkButton } from '@/components/ui/Button';
import { Panel } from '@/components/ui/Card';
import { EmptyState } from '@/components/ui/EmptyState';
import { Link } from '@/components/ui/Link';
import { PageHeader } from '@/components/ui/PageHeader';
import {
  EMPLOYEE_STATUS,
  useDepartments,
  useEmployees,
  type EmployeeStatus,
} from '@/features/team/api';
import { useAuth } from '@/lib/auth-context';
import { can, P } from '@/lib/permissions';

export function Component() {
  const { actor } = useAuth();
  const canManage = can(actor?.permissions ?? [], P.hrManage);
  const [params, setParams] = useSearchParams();
  const q = params.get('q') ?? '';
  const departmentId = params.get('department') ?? undefined;
  const status = (params.get('status') as EmployeeStatus | null) ?? undefined;
  const ids = { q: useId(), department: useId(), status: useId() };
  const departments = useDepartments();

  const set = (key: string, value: string | undefined) =>
    setParams((current) => {
      const next = new URLSearchParams(current);
      if (value) next.set(key, value);
      else next.delete(key);
      return next;
    });

  const [draft, setDraft] = useState(q);
  useEffect(() => {
    if (draft === q) return;
    const timer = window.setTimeout(() => set('q', draft.trim() || undefined), 300);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draft, q]);

  const employees = useEmployees({ q: q || undefined, department_id: departmentId, status });
  const filtered = Boolean(q || departmentId || status);

  return (
    <>
      <PageHeader
        title="Employees"
        description="The Delphin Digital team: who does what, and who reports to whom."
        actions={
          canManage ? (
            <LinkButton to="/team/employees/new" variant="primary">
              New employee
            </LinkButton>
          ) : null
        }
      />
      <div className="mb-3 flex flex-wrap items-end gap-3">
        <div className="label min-w-[240px] flex-1">
          <label htmlFor={ids.q}>Search</label>
          <input
            id={ids.q}
            type="search"
            className="input"
            placeholder="Name, employee ID or e-mail"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
          />
        </div>
        <div className="label">
          <label htmlFor={ids.department}>Department</label>
          <select
            id={ids.department}
            className="input"
            value={departmentId ?? ''}
            onChange={(event) => set('department', event.target.value || undefined)}
          >
            <option value="">All departments</option>
            {departments.data?.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>
        </div>
        <div className="label">
          <label htmlFor={ids.status}>Status</label>
          <select
            id={ids.status}
            className="input"
            value={status ?? ''}
            onChange={(event) => set('status', event.target.value || undefined)}
          >
            <option value="">All current</option>
            {(Object.keys(EMPLOYEE_STATUS) as EmployeeStatus[]).map((key) => (
              <option key={key} value={key}>
                {EMPLOYEE_STATUS[key].label}
              </option>
            ))}
          </select>
        </div>
      </div>
      <Panel flush>
        {employees.isPending ? <EmptyState title="Loading employees…" /> : null}
        {employees.isError ? (
          <EmptyState title="Couldn't load employees" description="Reload the page to try again." />
        ) : null}
        {employees.data?.length === 0 ? (
          <EmptyState
            title={filtered ? 'No employees match' : 'No employees yet'}
            description={filtered ? 'Try a different search or filter.' : 'HR adds employees here.'}
          />
        ) : null}
        {employees.data?.length ? (
          <div className="overflow-x-auto">
            <table className="table" data-testid="employees-table">
              <thead>
                <tr>
                  <th>Employee</th>
                  <th>Designation</th>
                  <th>Department</th>
                  <th>Reports to</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {employees.data.map((e) => (
                  <tr key={e.id}>
                    <td>
                      <Link className="link" to={`/team/employees/${e.id}`}>
                        {e.full_name}
                      </Link>
                      {e.is_me ? <span className="ml-1.5 text-xs text-muted">(you)</span> : null}
                      <div className="code">
                        {e.code}
                        {e.official_email ? ` · ${e.official_email}` : ''}
                      </div>
                    </td>
                    <td>{e.designation?.name ?? <span className="text-muted">—</span>}</td>
                    <td>{e.department?.name ?? <span className="text-muted">—</span>}</td>
                    <td>
                      {e.manager ? (
                        <Link className="link" to={`/team/employees/${e.manager.id}`}>
                          {e.manager.full_name}
                        </Link>
                      ) : (
                        <span className="text-muted">—</span>
                      )}
                    </td>
                    <td>
                      <Badge tone={EMPLOYEE_STATUS[e.status].tone}>{e.status_label}</Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </Panel>
    </>
  );
}
