/**
 * /team/teams: Organization & Role Settings (Organization brief §7–9). Everyone with
 * `org.view` sees the org chart, departments and designations; editing and the
 * other tabs follow the module's own permissions (never unrelated CRM access):
 * departments `org.departments.manage`, designations `org.designations.manage`,
 * reporting `org.reporting.manage` (or `org.projects.assign` for Project Manager
 * lines), roles `org.roles.manage` / `org.roles.assign`, audit `org.audit.view`.
 */
import { useSearchParams } from 'react-router';

import { Alert } from '@/components/ui/Alert';
import { Tabs } from '@/components/ui/Data';
import { PageHeader } from '@/components/ui/PageHeader';
import { useOrgChart } from '@/features/team/api';
import { AuditTab } from '@/features/team/org/AuditTab';
import { DepartmentsTab } from '@/features/team/org/DepartmentsTab';
import { DesignationsTab } from '@/features/team/org/DesignationsTab';
import { OrgChartView } from '@/features/team/org/OrgChartView';
import { ReportingEditor } from '@/features/team/org/ReportingEditor';
import { RolesTab } from '@/features/team/org/RolesTab';
import { useAuth } from '@/lib/auth-context';
import { can, canAny, P } from '@/lib/permissions';

type TabKey = 'chart' | 'departments' | 'designations' | 'reporting' | 'roles' | 'audit';

export function Component() {
  const { actor } = useAuth();
  const granted = actor?.permissions ?? [];
  const [params, setParams] = useSearchParams();
  const sees = can(granted, P.orgView);
  const chart = useOrgChart(sees);

  const tabs: { key: TabKey; label: string }[] = [
    { key: 'chart', label: 'Org chart' },
    { key: 'departments', label: 'Departments' },
    { key: 'designations', label: 'Designations' },
    ...(canAny(granted, [P.orgReportingManage, P.orgProjectsAssign])
      ? [{ key: 'reporting' as const, label: 'Reporting lines' }]
      : []),
    ...(canAny(granted, [P.orgRolesManage, P.orgRolesAssign])
      ? [{ key: 'roles' as const, label: 'Roles & permissions' }]
      : []),
    ...(can(granted, P.orgAuditView) ? [{ key: 'audit' as const, label: 'Audit log' }] : []),
  ];
  const requested = params.get('tab') as TabKey | null;
  const tab = tabs.some((t) => t.key === requested) ? (requested as TabKey) : 'chart';

  if (!sees) {
    return (
      <>
        <PageHeader title="Organization & Role Settings" />
        <Alert tone="bad" title="Access denied">
          You can't see the organisation structure.
        </Alert>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Organization & Role Settings"
        description="Departments, designations, reporting relationships and roles. Project Managers coordinate delivery; executive owners keep functional reporting."
      />
      <Tabs
        label="Organization settings"
        value={tab}
        onChange={(key) =>
          setParams((current) => {
            const next = new URLSearchParams(current);
            if (key === 'chart') next.delete('tab');
            else next.set('tab', key);
            return next;
          })
        }
        items={tabs}
      />
      {tab === 'chart' ? <OrgChartView chart={chart.data} /> : null}
      {tab === 'departments' ? (
        <DepartmentsTab manage={can(granted, P.orgDepartmentsManage)} />
      ) : null}
      {tab === 'designations' ? (
        <DesignationsTab manage={can(granted, P.orgDesignationsManage)} />
      ) : null}
      {tab === 'reporting' ? <ReportingEditor /> : null}
      {tab === 'roles' ? <RolesTab /> : null}
      {tab === 'audit' ? <AuditTab /> : null}
    </>
  );
}
