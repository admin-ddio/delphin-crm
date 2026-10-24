/**
 * /team/employees/:id: the employee profile (tab layout from the HR brief). Tabs the
 * viewer may not see are hidden (the API returns null for those sections). Phase 1
 * ships Overview, Personal, Employment, Projects & workload and Activity; the other
 * tabs say which HR phase brings them.
 */
import { useQuery } from '@tanstack/react-query';
import { useId, useState, type FormEvent } from 'react';
import { useParams, useSearchParams } from 'react-router';

import { Alert } from '@/components/ui/Alert';
import { Badge } from '@/components/ui/Badge';
import { Button, LinkButton } from '@/components/ui/Button';
import { Panel } from '@/components/ui/Card';
import { KeyValue, Tabs, Timeline } from '@/components/ui/Data';
import { EmptyState } from '@/components/ui/EmptyState';
import { Link } from '@/components/ui/Link';
import { PageHeader } from '@/components/ui/PageHeader';
import { useToast } from '@/components/ui/Toast';
import { TaskDrawer } from '@/features/tasks/TaskDrawer';
import { TaskTable } from '@/features/tasks/TaskTable';
import {
  EMPLOYEE_STATUS,
  EMPLOYMENT_TYPES,
  WORK_ARRANGEMENTS,
  useEmployee,
  useEmploymentHistory,
  useUpdateEmployee,
  useUpdatePersonal,
  type EmployeeDetail,
  type PersonalUpdate,
} from '@/features/team/api';
import { EmploymentForm, toBody, type EmploymentValues } from '@/features/team/EmploymentForm';
import { LineLegend, RelationList } from '@/features/team/org/Relations';
import { api, ApiError, unwrap } from '@/lib/api-client';
import { formatDate, formatDateTime } from '@/lib/format';

const crumb = { label: 'Employees', to: '/team/employees' };

type TabKey =
  | 'overview'
  | 'personal'
  | 'employment'
  | 'attendance'
  | 'leave'
  | 'documents'
  | 'performance'
  | 'work'
  | 'assets'
  | 'activity';

const LATER: Partial<Record<TabKey, [string, string]>> = {
  attendance: ['Attendance', 'Daily check-in/out and monthly summaries arrive in HR phase 4.'],
  leave: ['Leave', 'Leave balances, requests and approvals arrive in HR phase 3.'],
  documents: ['Documents', 'Offer letters, agreements and acknowledgements arrive in HR phase 2.'],
  performance: ['Performance', 'Probation and performance reviews arrive in HR phase 5.'],
  assets: ['Assets & access', 'Equipment and account access tracking arrives in HR phase 5.'],
};

function errorMessage(error: unknown) {
  return error instanceof ApiError ? error.message : 'Something went wrong. Try again.';
}

function person(ref: { id: string; full_name: string; code: string } | null | undefined) {
  return ref ? (
    <Link className="link" to={`/team/employees/${ref.id}`}>
      {ref.full_name}
    </Link>
  ) : null;
}

function Overview({ employee }: { employee: EmployeeDetail }) {
  const e = employee.employment;
  return (
    <div className="grid grid-cols-[repeat(auto-fit,minmax(300px,1fr))] items-start gap-4">
      <Panel title="Overview">
        <KeyValue
          items={[
            [
              'Employee ID',
              <span key="c" className="code">
                {employee.code}
              </span>,
            ],
            ['Designation', employee.designation?.name],
            ['Department', employee.department?.name],
            ['Status', employee.status_label],
            ['Official e-mail', employee.official_email],
            ['Direct manager', person(employee.manager)],
            ...(e
              ? ([
                  ['Department head', person(e.department_head)],
                  [
                    'Functional manager',
                    e.reporting
                      .filter((r) => r.kind === 'functional_manager')
                      .map((r) => r.manager.full_name)
                      .join(', ') || null,
                  ],
                  [
                    'Project manager',
                    e.reporting
                      .filter((r) => r.kind === 'project_manager')
                      .map((r) => r.manager.full_name + (r.project ? ` (${r.project.name})` : ''))
                      .join(', ') || null,
                  ],
                  ['Joining date', e.joining_date ? formatDate(e.joining_date) : null],
                  [
                    'Work arrangement',
                    WORK_ARRANGEMENTS.find((w) => w.value === e.work_arrangement)?.label,
                  ],
                  [
                    'Employment type',
                    EMPLOYMENT_TYPES.find((t) => t.value === e.employment_type)?.label,
                  ],
                ] as [string, React.ReactNode][])
              : []),
          ]}
        />
      </Panel>
      <Panel title="Direct reports" flush>
        {employee.direct_reports.length ? (
          <ul className="flex flex-col gap-1.5 p-3.5">
            {employee.direct_reports.map((r) => (
              <li key={r.id}>
                {person(r)} <span className="code">{r.code}</span>
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState title="No direct reports" />
        )}
      </Panel>
    </div>
  );
}

const PERSONAL_FIELDS: {
  key: keyof PersonalUpdate;
  label: string;
  type?: string;
  long?: boolean;
}[] = [
  { key: 'preferred_name', label: 'Preferred name' },
  { key: 'personal_email', label: 'Personal e-mail', type: 'email' },
  { key: 'phone', label: 'Phone', type: 'tel' },
  { key: 'date_of_birth', label: 'Date of birth', type: 'date' },
  { key: 'current_address', label: 'Current address', long: true },
  { key: 'permanent_address', label: 'Permanent address', long: true },
  { key: 'emergency_name', label: 'Emergency contact' },
  { key: 'emergency_relationship', label: 'Relationship' },
  { key: 'emergency_phone', label: 'Emergency phone', type: 'tel' },
];

function Personal({ employee }: { employee: EmployeeDetail }) {
  const personal = employee.personal;
  const save = useUpdatePersonal(employee.id);
  const { toast } = useToast();
  const id = useId();
  const [editing, setEditing] = useState(false);
  const current = (key: keyof PersonalUpdate) =>
    (key === 'preferred_name' ? employee.preferred_name : personal?.[key]) ?? '';
  const [values, setValues] = useState<Record<string, string>>({});
  if (!personal) return null;

  const start = () => {
    setValues(Object.fromEntries(PERSONAL_FIELDS.map((f) => [f.key, current(f.key)])));
    setEditing(true);
  };
  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      await save.mutateAsync(
        Object.fromEntries(PERSONAL_FIELDS.map((f) => [f.key, values[f.key] || null])),
      );
      toast({ title: 'Personal details saved.' });
      setEditing(false);
    } catch (error) {
      toast({ title: errorMessage(error), tone: 'error' });
    }
  }

  return (
    <Panel
      title="Personal information"
      description="Visible only to the employee and to HR."
      actions={
        employee.permissions.edit_personal && !editing ? (
          <Button size="sm" onClick={start}>
            Edit personal details
          </Button>
        ) : null
      }
    >
      {editing ? (
        <form className="flex max-w-3xl flex-col gap-3" onSubmit={submit}>
          <div className="grid grid-cols-[repeat(auto-fit,minmax(220px,1fr))] gap-3">
            {PERSONAL_FIELDS.map((f) => (
              <div key={f.key} className={f.long ? 'label col-span-full' : 'label'}>
                <label htmlFor={`${id}-${f.key}`}>{f.label}</label>
                {f.long ? (
                  <textarea
                    id={`${id}-${f.key}`}
                    className="input min-h-16"
                    maxLength={1000}
                    value={values[f.key]}
                    onChange={(e) => setValues((v) => ({ ...v, [f.key]: e.target.value }))}
                  />
                ) : (
                  <input
                    id={`${id}-${f.key}`}
                    type={f.type ?? 'text'}
                    className="input"
                    value={values[f.key]}
                    onChange={(e) => setValues((v) => ({ ...v, [f.key]: e.target.value }))}
                  />
                )}
              </div>
            ))}
          </div>
          <div className="flex gap-2">
            <Button type="submit" variant="primary" disabled={save.isPending}>
              Save personal details
            </Button>
            <Button type="button" onClick={() => setEditing(false)}>
              Cancel
            </Button>
          </div>
        </form>
      ) : (
        <KeyValue
          items={PERSONAL_FIELDS.map((f) => [
            f.label,
            f.type === 'date' && current(f.key) ? formatDate(current(f.key)) : current(f.key),
          ])}
        />
      )}
    </Panel>
  );
}

/** Every relationship that applies, explicit or inherited from the department. */
function ReportingRelations({ employee }: { employee: EmployeeDetail }) {
  const relations = employee.employment?.reporting ?? [];
  return (
    <Panel
      title="Reporting relationships"
      description="Delivery, functional and approval lines. Department defaults apply unless set on the employee."
      actions={
        employee.permissions.manage_reporting ? (
          <LinkButton size="sm" to={`/team/teams?tab=reporting&employee=${employee.id}`}>
            Edit reporting
          </LinkButton>
        ) : null
      }
    >
      <RelationList relations={relations} />
      <div className="mt-3">
        <LineLegend />
      </div>
    </Panel>
  );
}

function Employment({ employee }: { employee: EmployeeDetail }) {
  const e = employee.employment;
  const update = useUpdateEmployee(employee.id);
  const { toast } = useToast();
  const [editing, setEditing] = useState(false);
  if (!e) return null;
  const initial: EmploymentValues = {
    full_name: employee.full_name,
    official_email: employee.official_email ?? '',
    department_id: employee.department?.id ?? '',
    designation_id: employee.designation?.id ?? '',
    employment_type: e.employment_type,
    work_arrangement: e.work_arrangement ?? '',
    status: employee.status,
    joining_date: e.joining_date ?? '',
    manager_id: employee.manager?.id ?? '',
    user_id: employee.user_id ?? '',
  };
  return (
    <div className="flex flex-col gap-4">
      <Panel
        title="Employment"
        actions={
          (employee.permissions.manage || employee.permissions.manage_reporting) && !editing ? (
            <Button size="sm" onClick={() => setEditing(true)}>
              Edit employment
            </Button>
          ) : null
        }
      >
        {editing ? (
          <EmploymentForm
            initial={initial}
            employeeId={employee.id}
            placement={employee.permissions.manage_reporting}
            record={employee.permissions.manage}
            currentAccount={
              employee.user_id ? { id: employee.user_id, label: 'Current account' } : undefined
            }
            submitLabel="Save employment"
            onCancel={() => setEditing(false)}
            onSubmit={async (values) => {
              try {
                await update.mutateAsync(
                  toBody(values, {
                    placement: employee.permissions.manage_reporting,
                    record: employee.permissions.manage,
                  }),
                );
                toast({ title: 'Employment updated.' });
                setEditing(false);
              } catch (error) {
                toast({ title: errorMessage(error), tone: 'error' });
              }
            }}
          />
        ) : (
          <KeyValue
            items={[
              [
                'Employment type',
                EMPLOYMENT_TYPES.find((t) => t.value === e.employment_type)?.label,
              ],
              [
                'Work arrangement',
                WORK_ARRANGEMENTS.find((w) => w.value === e.work_arrangement)?.label,
              ],
              ['Joining date', e.joining_date ? formatDate(e.joining_date) : null],
              ['Direct manager', person(employee.manager)],
              ['Department head', person(e.department_head)],
              [
                'Leave approver',
                e.effective_leave_approver ? (
                  person(e.effective_leave_approver)
                ) : (
                  <span className="text-muted">Not set</span>
                ),
              ],
              ['Sign-in account', e.has_account ? 'Linked' : 'Not linked'],
            ]}
          />
        )}
      </Panel>
      <ReportingRelations employee={employee} />
    </div>
  );
}

function Work({ employee }: { employee: EmployeeDetail }) {
  const [open, setOpen] = useState<string | null>(null);
  const userId = employee.user_id;
  const tasks = useQuery({
    queryKey: ['tasks', 'list', 'assignee', userId],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/tasks', {
          params: { query: { view: 'all', assignee_id: userId ?? undefined } },
        }),
      ),
    enabled: Boolean(userId),
  });
  if (!userId) {
    return (
      <Panel flush>
        <EmptyState
          title="No sign-in account linked"
          description="Projects and tasks appear once the employee has an account."
        />
      </Panel>
    );
  }
  return (
    <Panel
      title="Projects & workload"
      description="Open tasks assigned to this person on projects you can see."
      flush
    >
      {tasks.isPending ? <EmptyState title="Loading…" /> : null}
      {tasks.data?.length === 0 ? <EmptyState title="No open tasks" /> : null}
      {tasks.data?.length ? <TaskTable tasks={tasks.data} onOpen={setOpen} /> : null}
      <TaskDrawer taskId={open} onClose={() => setOpen(null)} />
    </Panel>
  );
}

function Activity({ employee }: { employee: EmployeeDetail }) {
  const history = useEmploymentHistory(employee.id, Boolean(employee.employment));
  return (
    <Panel title="Activity history">
      {history.isPending ? <p className="text-muted">Loading…</p> : null}
      {history.data?.length === 0 ? <EmptyState title="No activity yet" /> : null}
      {history.data?.length ? (
        <Timeline
          entries={history.data.map((h) => ({
            id: h.id,
            text: h.summary,
            meta: `${h.actor ?? 'System'} · ${formatDateTime(h.occurred_at)}`,
          }))}
        />
      ) : null}
    </Panel>
  );
}

export function Component() {
  const { id = '' } = useParams();
  const [params, setParams] = useSearchParams();
  const employee = useEmployee(id);

  if (employee.isPending) return <PageHeader title="Loading…" crumb={crumb} />;
  if (!employee.data) {
    return (
      <>
        <PageHeader title="Employee not found" crumb={crumb} />
        <Alert tone="bad">This employee doesn't exist.</Alert>
      </>
    );
  }
  const data = employee.data;
  const sensitive = Boolean(data.employment);
  const tabs: { key: TabKey; label: string }[] = [
    { key: 'overview', label: 'Overview' },
    ...(data.personal ? [{ key: 'personal' as const, label: 'Personal' }] : []),
    ...(sensitive
      ? [
          { key: 'employment' as const, label: 'Employment' },
          { key: 'attendance' as const, label: 'Attendance' },
          { key: 'leave' as const, label: 'Leave' },
          { key: 'documents' as const, label: 'Documents' },
          { key: 'performance' as const, label: 'Performance' },
        ]
      : []),
    { key: 'work', label: 'Projects & workload' },
    ...(sensitive
      ? [
          { key: 'assets' as const, label: 'Assets & access' },
          { key: 'activity' as const, label: 'Activity' },
        ]
      : []),
  ];
  const requested = params.get('tab') as TabKey | null;
  const tab = tabs.some((t) => t.key === requested) ? (requested as TabKey) : 'overview';
  const later = LATER[tab];

  return (
    <>
      <PageHeader
        crumb={crumb}
        title={
          <span className="flex flex-wrap items-center gap-2">
            {data.full_name}
            {data.preferred_name ? (
              <span className="text-base font-normal text-muted">“{data.preferred_name}”</span>
            ) : null}
            <Badge tone={EMPLOYEE_STATUS[data.status].tone}>{data.status_label}</Badge>
          </span>
        }
        description={
          <>
            <span className="code">{data.code}</span>
            {data.designation ? ` · ${data.designation.name}` : ''}
            {data.department ? ` · ${data.department.name}` : ''}
          </>
        }
      />
      <Tabs
        label="Employee sections"
        value={tab}
        onChange={(key) =>
          setParams((current) => {
            const next = new URLSearchParams(current);
            if (key === 'overview') next.delete('tab');
            else next.set('tab', key);
            return next;
          })
        }
        items={tabs}
      />
      {tab === 'overview' ? <Overview employee={data} /> : null}
      {tab === 'personal' ? <Personal employee={data} /> : null}
      {tab === 'employment' ? <Employment employee={data} /> : null}
      {tab === 'work' ? <Work employee={data} /> : null}
      {tab === 'activity' ? <Activity employee={data} /> : null}
      {later ? (
        <Panel flush>
          <EmptyState title={`${later[0]} isn't built yet`} description={later[1]} />
        </Panel>
      ) : null}
    </>
  );
}
