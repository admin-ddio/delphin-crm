/** Organisation audit log (`org.audit.view`): departments, designations, reporting, roles. */
import { useMemo, useState } from 'react';

import { Panel } from '@/components/ui/Card';
import { EmptyState } from '@/components/ui/EmptyState';
import { SelectField } from '@/components/ui/Fields';
import { useOrgAudit, type OrgAuditEntry } from '@/features/team/api';
import { formatDateTime } from '@/lib/format';

const ACTIONS: Record<string, string> = {
  'department.created': 'Department created',
  'department.updated': 'Department changed',
  'designation.created': 'Designation created',
  'designation.updated': 'Designation changed',
  'reporting.changed': 'Reporting changed',
  'role.created': 'Role created',
  'role.updated': 'Role changed',
  'user.roles_changed': 'Roles assigned',
  'employee.created': 'Employee added',
  'employee.placement_changed': 'Placement changed',
};

const GROUPS = [
  { value: 'department.', label: 'Departments' },
  { value: 'designation.', label: 'Designations' },
  { value: 'employee.', label: 'Employees' },
  { value: 'reporting.', label: 'Reporting' },
  { value: 'role.', label: 'Roles' },
  { value: 'user.', label: 'Role assignments' },
];

function describe(entry: OrgAuditEntry): string {
  const subject = String(entry.context.name ?? entry.context.code ?? entry.context.key ?? '');
  const c = entry.changes as Record<string, unknown>;
  const list = (value: unknown) =>
    Array.isArray(value)
      ? value
          .map((v) =>
            typeof v === 'object' && v && 'kind_label' in v
              ? `${String((v as { kind_label: string }).kind_label)}: ${String(
                  (v as { manager: { full_name: string } }).manager.full_name,
                )}`
              : String(v),
          )
          .join(', ')
      : '';
  const parts: string[] = [];
  if (entry.action === 'reporting.changed') {
    if (list(c.added)) parts.push(`added ${list(c.added)}`);
    if (list(c.ended)) parts.push(`ended ${list(c.ended)}`);
    if (c.effective_on) parts.push(`from ${String(c.effective_on)}`);
  } else if (entry.action === 'role.updated') {
    if (list(c.added)) parts.push(`granted ${list(c.added)}`);
    if (list(c.removed)) parts.push(`removed ${list(c.removed)}`);
    if (c.name) parts.push('renamed');
  } else if (entry.action === 'user.roles_changed' && Array.isArray(c.roles)) {
    parts.push(`${list(c.roles[0])} → ${list(c.roles[1])}`);
  } else {
    parts.push(
      Object.keys(c)
        .map((k) => k.replace(/_ids?$/, '').replace(/_/g, ' '))
        .join(', '),
    );
  }
  return [subject, parts.filter(Boolean).join('; ')].filter(Boolean).join(': ');
}

export function AuditTab() {
  const audit = useOrgAudit(true);
  const [group, setGroup] = useState('');
  const rows = useMemo(
    () => (audit.data ?? []).filter((e) => !group || e.action.startsWith(group)),
    [audit.data, group],
  );
  return (
    <Panel
      title="Audit log"
      description="Every change to the organisation, newest first."
      flush
      actions={
        <div className="w-52">
          <SelectField
            label="Show"
            placeholder="Everything"
            value={group}
            onChange={(e) => setGroup(e.target.value)}
            options={GROUPS}
          />
        </div>
      }
    >
      {audit.isPending ? <EmptyState title="Loading…" /> : null}
      {rows.length ? (
        <div className="overflow-x-auto">
          <table className="table" data-testid="org-audit">
            <thead>
              <tr>
                <th>When</th>
                <th>Who</th>
                <th>What</th>
                <th>Details</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((entry) => (
                <tr key={entry.id}>
                  <td className="whitespace-nowrap text-muted">
                    {formatDateTime(entry.occurred_at)}
                  </td>
                  <td>{entry.actor ?? 'System'}</td>
                  <td className="whitespace-nowrap">{ACTIONS[entry.action] ?? entry.action}</td>
                  <td className="text-[13px]">{describe(entry)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : audit.data ? (
        <EmptyState title="No changes recorded yet" />
      ) : null}
    </Panel>
  );
}
