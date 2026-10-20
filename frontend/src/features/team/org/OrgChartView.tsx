/**
 * The organisation chart (Organization brief §9). Two views:
 * - Executive hierarchy: founders, then departments with their executive owners,
 *   head, default Project Manager and members with their reporting lines;
 * - Project delivery: Project Managers and the people / projects they coordinate.
 * Relationships use distinct line styles AND text labels. Unassigned owners, heads
 * and unresolved reporting are flagged. Filters: department, designation, manager,
 * status, reporting type. Also renders a preview (`chart` passed in).
 */
import { AlertTriangle, ChevronDown, ChevronRight } from 'lucide-react';
import { useMemo, useState } from 'react';

import { Avatar } from '@/components/ui/Avatar';
import { Badge } from '@/components/ui/Badge';
import { Panel } from '@/components/ui/Card';
import { Tabs } from '@/components/ui/Data';
import { EmptyState } from '@/components/ui/EmptyState';
import { SelectField } from '@/components/ui/Fields';
import { Link } from '@/components/ui/Link';
import {
  EMPLOYEE_STATUS,
  REPORTING_KINDS,
  type ChartDepartment,
  type ChartMember,
  type EmployeeStatus,
  type OrgChart,
  type ReportingKind,
} from '@/features/team/api';
import { LineLegend, LineSample, RelationList } from '@/features/team/org/Relations';
import { cn } from '@/lib/utils';

type View = 'executive' | 'delivery';

interface Filters {
  department: string;
  designation: string;
  manager: string;
  status: string;
  kind: string;
}

const NO_FILTERS: Filters = { department: '', designation: '', manager: '', status: '', kind: '' };

function matches(member: ChartMember, f: Filters) {
  if (f.department && member.department_id !== f.department) return false;
  if (f.designation && member.designation?.id !== f.designation) return false;
  if (f.status && member.status !== f.status) return false;
  const relations = f.kind ? member.relations.filter((r) => r.kind === f.kind) : member.relations;
  if (f.kind && !relations.length) return false;
  if (f.manager && !relations.some((r) => r.manager.id === f.manager)) return false;
  return true;
}

function Issues({ issues }: { issues: readonly string[] }) {
  if (!issues.length) return null;
  return (
    <>
      {issues.map((issue) => (
        <Badge key={issue} tone="warn">
          <AlertTriangle aria-hidden className="size-3" />
          {issue}
        </Badge>
      ))}
    </>
  );
}

function MemberRow({ member, kind }: { member: ChartMember; kind: string }) {
  const relations = kind ? member.relations.filter((r) => r.kind === kind) : member.relations;
  // Approver fallbacks repeat the line managers: keep the chart to the structural lines.
  const shown = kind
    ? relations
    : relations.filter((r) =>
        ['direct_manager', 'functional_manager', 'project_manager'].includes(r.kind),
      );
  return (
    <li className="flex flex-col gap-1 border-t border-line-soft py-2.5 first:border-t-0">
      <div className="flex flex-wrap items-center gap-2">
        <Avatar name={member.full_name} size="xs" />
        <Link className="link font-medium" to={`/team/employees/${member.id}`}>
          {member.full_name}
        </Link>
        <span className="text-[12.5px] text-muted">
          {member.designation?.name ?? 'No designation'}
        </span>
        {member.status !== 'active' ? (
          <Badge tone={EMPLOYEE_STATUS[member.status].tone}>{member.status_label}</Badge>
        ) : null}
        <Issues issues={member.issues} />
      </div>
      <div className="pl-9">
        <RelationList relations={shown} compact empty="No reporting lines." />
      </div>
    </li>
  );
}

function DepartmentCard({
  department,
  members,
  kind,
  initiallyOpen,
}: {
  department: ChartDepartment;
  members: ChartMember[];
  kind: string;
  initiallyOpen: boolean;
}) {
  const [open, setOpen] = useState(initiallyOpen);
  const owners = department.owners;
  return (
    <section
      className={cn('card', !department.is_active && 'opacity-70')}
      data-testid="chart-department"
      aria-label={department.name}
    >
      <header className="flex flex-wrap items-center gap-2 px-4 py-3">
        <button
          type="button"
          className="flex cursor-pointer items-center gap-1.5 text-left font-semibold"
          aria-expanded={open}
          onClick={() => setOpen(!open)}
        >
          {open ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
          {department.name}
        </button>
        <span className="code">{members.length}</span>
        {!department.is_active ? <Badge>Inactive</Badge> : null}
        <Issues issues={department.issues} />
      </header>
      <dl className="grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-x-4 gap-y-1 border-t border-line-soft px-4 py-2.5 text-[12.5px]">
        <div className="flex items-center gap-1.5">
          <LineSample kind="functional_manager" />
          <dt className="text-muted">Functional owner{owners.length > 1 ? 's' : ''}:</dt>
          <dd className="font-medium">
            {owners.length ? owners.map((o) => o.full_name).join(' & ') : 'Unassigned'}
          </dd>
        </div>
        <div className="flex items-center gap-1.5">
          <LineSample kind="department_head" />
          <dt className="text-muted">Head:</dt>
          <dd className="font-medium">{department.head?.full_name ?? 'Unassigned'}</dd>
        </div>
        <div className="flex items-center gap-1.5">
          <LineSample kind="project_manager" />
          <dt className="text-muted">Delivery via:</dt>
          <dd className="font-medium">{department.delivery_manager?.full_name ?? 'Unassigned'}</dd>
        </div>
      </dl>
      {open ? (
        members.length ? (
          <ul className="border-t border-line-soft px-4">
            {members.map((m) => (
              <MemberRow key={m.id} member={m} kind={kind} />
            ))}
          </ul>
        ) : (
          <p className="border-t border-line-soft px-4 py-3 text-[12.5px] text-muted">
            No members{kind ? ' with this relationship' : ''}.
          </p>
        )
      ) : null}
    </section>
  );
}

function Executive({ chart, filters }: { chart: OrgChart; filters: Filters }) {
  const filtering = Object.values(filters).some(Boolean);
  const owned = (id: string) =>
    chart.departments.filter((d) => d.owners.some((o) => o.id === id)).map((d) => d.name);
  const departments = chart.departments.filter(
    (d) => !filters.department || d.id === filters.department,
  );
  const unplaced = chart.unplaced.filter((m) => matches(m, filters));
  return (
    <div className="flex flex-col gap-4">
      <Panel
        title="Executive leadership"
        description="Founders sit side by side; none reports to another unless configured."
      >
        {chart.executives.length ? (
          <ul
            className="grid grid-cols-[repeat(auto-fit,minmax(220px,1fr))] gap-3"
            data-testid="executives"
          >
            {chart.executives.map((e) => (
              <li key={e.id} className="flex items-start gap-3 rounded-lg border border-line p-3">
                <Avatar name={e.full_name} size="md" />
                <div className="min-w-0">
                  <Link className="link font-semibold" to={`/team/employees/${e.id}`}>
                    {e.full_name}
                  </Link>
                  <div className="text-[12.5px] text-muted">{e.designation?.name}</div>
                  <div className="mt-1 text-xs">
                    {owned(e.id).length ? (
                      <>Owns: {owned(e.id).join(', ')}</>
                    ) : (
                      <span className="text-muted">No departments assigned</span>
                    )}
                  </div>
                  {e.relations.length ? (
                    <div className="mt-1">
                      <RelationList relations={e.relations} compact />
                    </div>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState
            title="No executives marked"
            description="Mark the founders as executive leadership on their employee records."
          />
        )}
      </Panel>
      <div className="grid gap-3 xl:grid-cols-2">
        {departments.map((d) => {
          const members = d.members.filter((m) => matches(m, filters));
          if (filtering && !members.length && !filters.department) return null;
          return (
            <DepartmentCard
              key={d.id}
              department={d}
              members={members}
              kind={filters.kind}
              initiallyOpen={filtering || members.length > 0}
            />
          );
        })}
      </div>
      {unplaced.length ? (
        <Panel title="Not in a department" description="Assign these people a department.">
          <ul>
            {unplaced.map((m) => (
              <MemberRow key={m.id} member={m} kind={filters.kind} />
            ))}
          </ul>
        </Panel>
      ) : null}
    </div>
  );
}

function Delivery({ chart, filters }: { chart: OrgChart; filters: Filters }) {
  const members = new Map(
    [...chart.departments.flatMap((d) => d.members), ...chart.unplaced, ...chart.executives].map(
      (m) => [m.id, m],
    ),
  );
  const keep = (id: string) => {
    const m = members.get(id);
    return !m || matches(m, { ...filters, kind: '', manager: '' });
  };
  const groups = chart.delivery.filter((g) => !filters.manager || g.manager.id === filters.manager);
  if (!groups.length) {
    return (
      <Panel flush>
        <EmptyState
          title="No project delivery lines"
          description="Set a default Project Manager on departments, or assign Project Managers to employees."
        />
      </Panel>
    );
  }
  return (
    <div className="grid gap-3 xl:grid-cols-2" data-testid="delivery">
      {groups.map((g) => {
        const general = g.members.filter((p) => keep(p.id));
        return (
          <Panel
            key={g.manager.id}
            title={
              <span className="flex items-center gap-2">
                <Avatar name={g.manager.full_name} size="xs" />
                <Link className="link" to={`/team/employees/${g.manager.id}`}>
                  {g.manager.full_name}
                </Link>
              </span>
            }
            description="Project Manager"
          >
            <div className="flex flex-col gap-3">
              <div>
                <h3 className="mb-1 flex items-center gap-1.5 text-[12.5px] font-semibold">
                  <LineSample kind="project_manager" /> Delivery for (department default or general
                  assignment)
                </h3>
                {general.length ? (
                  <p className="text-[13px]">{general.map((p) => p.full_name).join(', ')}</p>
                ) : (
                  <p className="text-[12.5px] text-muted">Nobody.</p>
                )}
              </div>
              {g.projects.map((p) => {
                const people = p.members.filter((m) => keep(m.id));
                return (
                  <div
                    key={p.project.id}
                    className="rounded-lg border border-dotted border-line p-2.5"
                  >
                    <h3 className="flex flex-wrap items-center gap-1.5 text-[12.5px] font-semibold">
                      <LineSample kind="project_manager" /> Project:{' '}
                      {p.project.code ? <span className="code">{p.project.code}</span> : null}
                      {p.project.name}
                    </h3>
                    <p className="mt-1 text-[13px]">
                      {people.length
                        ? people.map((m) => m.full_name).join(', ')
                        : 'Nobody assigned.'}
                    </p>
                  </div>
                );
              })}
            </div>
          </Panel>
        );
      })}
    </div>
  );
}

export function OrgChartView({
  chart,
  preview = false,
}: {
  chart: OrgChart | undefined;
  preview?: boolean;
}) {
  const [view, setView] = useState<View>('executive');
  const [filters, setFilters] = useState<Filters>(NO_FILTERS);
  const everyone = useMemo(
    () =>
      chart
        ? [...chart.executives, ...chart.departments.flatMap((d) => d.members), ...chart.unplaced]
        : [],
    [chart],
  );
  const designations = useMemo(() => {
    const seen = new Map<string, string>();
    for (const m of everyone) if (m.designation) seen.set(m.designation.id, m.designation.name);
    return [...seen]
      .map(([value, label]) => ({ value, label }))
      .sort((a, b) => a.label.localeCompare(b.label));
  }, [everyone]);
  if (!chart) return <EmptyState title="Loading…" />;
  const set = (key: keyof Filters) => (e: { target: { value: string } }) =>
    setFilters((f) => ({ ...f, [key]: e.target.value }));
  const statuses = Object.keys(EMPLOYEE_STATUS).filter((s) => s !== 'exited') as EmployeeStatus[];

  return (
    <div className="flex flex-col gap-4" data-testid={preview ? 'chart-preview' : 'org-chart'}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Tabs
          label="Chart view"
          value={view}
          onChange={(key) => setView(key as View)}
          items={[
            { key: 'executive', label: 'Executive hierarchy' },
            { key: 'delivery', label: 'Project delivery' },
          ]}
        />
        <LineLegend />
      </div>
      <div
        className="grid grid-cols-[repeat(auto-fit,minmax(170px,1fr))] gap-3"
        aria-label="Chart filters"
      >
        <SelectField
          label="Department"
          placeholder="All departments"
          value={filters.department}
          onChange={set('department')}
          options={chart.departments.map((d) => ({ value: d.id, label: d.name }))}
        />
        <SelectField
          label="Designation"
          placeholder="All designations"
          value={filters.designation}
          onChange={set('designation')}
          options={designations}
        />
        <SelectField
          label="Manager"
          placeholder="Anyone"
          value={filters.manager}
          onChange={set('manager')}
          options={everyone
            .map((m) => ({ value: m.id, label: m.full_name }))
            .sort((a, b) => a.label.localeCompare(b.label))}
        />
        <SelectField
          label="Status"
          placeholder="Any status"
          value={filters.status}
          onChange={set('status')}
          options={statuses.map((s) => ({ value: s, label: EMPLOYEE_STATUS[s].label }))}
        />
        <SelectField
          label="Reporting type"
          placeholder="All relationships"
          value={filters.kind}
          onChange={set('kind')}
          options={REPORTING_KINDS.map((k) => ({ value: k.value, label: k.label }))}
        />
      </div>
      {view === 'executive' ? (
        <Executive chart={chart} filters={filters} />
      ) : (
        <Delivery chart={chart} filters={filters} />
      )}
    </div>
  );
}

export type { ReportingKind };
