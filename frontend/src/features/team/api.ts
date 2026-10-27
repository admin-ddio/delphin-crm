/** Typed TanStack Query hooks for the team module: people core (types from the generated schema). */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type { components } from '@/api/schema';
import type { BadgeTone } from '@/components/ui/Badge';
import { api, unwrap } from '@/lib/api-client';

export type EmployeeListItem = components['schemas']['EmployeeListItem'];
export type EmployeeDetail = components['schemas']['EmployeeDetail'];
export type EmployeeCreate = components['schemas']['EmployeeCreate'];
export type EmployeeUpdate = components['schemas']['EmployeeUpdate'];
export type PersonalUpdate = components['schemas']['PersonalUpdate'];
export type EmployeeStatus = EmployeeListItem['status'];
export type EmploymentType = EmployeeCreate['employment_type'];
export type WorkArrangement = NonNullable<EmployeeCreate['work_arrangement']>;
export type Department = components['schemas']['DepartmentOut'];
export type Designation = components['schemas']['DesignationOut'];
export type Relation = components['schemas']['Relation'];
export type ReportingKind = Relation['kind'];
export type Reporting = components['schemas']['Reporting'];
export type ReportingLineOut = components['schemas']['ReportingLineOut'];
export type ReportingChange = components['schemas']['ReportingChange'];
export type ReportingLineIn = components['schemas']['ReportingLineIn'];
export type ReportingPreview = components['schemas']['ReportingPreview'];
export type OrgChart = components['schemas']['OrgChart'];
export type ChartMember = components['schemas']['ChartMember'];
export type ChartDepartment = components['schemas']['ChartDepartment'];
export type DeliveryGroup = components['schemas']['DeliveryGroup'];
export type ProjectOption = components['schemas']['ProjectOption'];
export type RolesOverview = components['schemas']['RolesOverview'];
export type RoleOut = components['schemas']['RoleOut'];
export type UserRoles = components['schemas']['UserRoles'];
export type OrgAuditEntry = components['schemas']['OrgAuditEntry'];

export interface DirectoryParams {
  q?: string;
  department_id?: string;
  designation_id?: string;
  status?: EmployeeStatus;
  include_exited?: boolean;
}

export const teamKeys = {
  all: ['team'] as const,
  employees: (params: DirectoryParams = {}) => ['team', 'employees', params] as const,
  employee: (id: string) => ['team', 'employee', id] as const,
  history: (id: string) => ['team', 'history', id] as const,
  userOptions: ['team', 'user-options'] as const,
  departments: ['team', 'departments'] as const,
  designations: ['team', 'designations'] as const,
  reporting: (id: string) => ['team', 'reporting', id] as const,
  orgChart: ['team', 'org-chart'] as const,
  projectOptions: ['team', 'project-options'] as const,
  roles: ['team', 'roles'] as const,
  users: ['team', 'users'] as const,
  audit: ['team', 'org-audit'] as const,
};

/** The seven relationship types, in display order (Organization brief §6). */
export const REPORTING_KINDS: { value: ReportingKind; label: string; multi: boolean }[] = [
  { value: 'direct_manager', label: 'Direct manager', multi: false },
  { value: 'functional_manager', label: 'Functional manager', multi: true },
  { value: 'project_manager', label: 'Project manager', multi: true },
  { value: 'department_head', label: 'Department head', multi: false },
  { value: 'leave_approver', label: 'Leave approver', multi: false },
  { value: 'performance_reviewer', label: 'Performance reviewer', multi: false },
  { value: 'executive_escalation', label: 'Executive escalation', multi: false },
];

/** Line styles and text labels per relationship: the chart never relies on colour alone. */
export const LINE_STYLE: Record<ReportingKind, { border: string; short: string }> = {
  direct_manager: { border: 'border-solid', short: 'Direct' },
  functional_manager: { border: 'border-dashed', short: 'Functional' },
  project_manager: { border: 'border-dotted', short: 'Project' },
  department_head: { border: 'border-double', short: 'Head' },
  leave_approver: { border: 'border-solid', short: 'Leave' },
  performance_reviewer: { border: 'border-solid', short: 'Review' },
  executive_escalation: { border: 'border-solid', short: 'Escalation' },
};

export const SOURCE_LABELS: Record<Relation['source'], string> = {
  explicit: 'set on the employee',
  department: 'department default',
  direct_manager: 'via the direct manager',
  functional_manager: 'via the functional manager',
};

export const EMPLOYEE_STATUS: Record<EmployeeStatus, { label: string; tone: BadgeTone }> = {
  onboarding: { label: 'Onboarding', tone: 'accent' },
  probation: { label: 'On probation', tone: 'info' },
  active: { label: 'Active', tone: 'ok' },
  notice: { label: 'Notice period', tone: 'warn' },
  on_hold: { label: 'On hold', tone: 'warn' },
  exited: { label: 'Exited', tone: 'neutral' },
};

export const EMPLOYMENT_TYPES: { value: EmploymentType; label: string }[] = [
  { value: 'full_time', label: 'Full-time' },
  { value: 'part_time', label: 'Part-time' },
  { value: 'intern', label: 'Intern' },
  { value: 'contractor', label: 'Contractor' },
  { value: 'consultant', label: 'Consultant' },
];

export const WORK_ARRANGEMENTS: { value: WorkArrangement; label: string }[] = [
  { value: 'office', label: 'Office' },
  { value: 'hybrid', label: 'Hybrid' },
  { value: 'remote', label: 'Remote' },
];

export function useEmployees(params: DirectoryParams = {}) {
  return useQuery({
    queryKey: teamKeys.employees(params),
    queryFn: async () =>
      unwrap(await api.GET('/api/v1/team/employees', { params: { query: params } })),
  });
}

export function useEmployee(id: string) {
  return useQuery({
    queryKey: teamKeys.employee(id),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/team/employees/{employee_id}', {
          params: { path: { employee_id: id } },
        }),
      ),
  });
}

export function useEmploymentHistory(id: string, enabled: boolean) {
  return useQuery({
    queryKey: teamKeys.history(id),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/team/employees/{employee_id}/history', {
          params: { path: { employee_id: id } },
        }),
      ),
    enabled,
  });
}

export function useUserOptions(enabled: boolean) {
  return useQuery({
    queryKey: teamKeys.userOptions,
    queryFn: async () => unwrap(await api.GET('/api/v1/team/employees/user-options')),
    enabled,
  });
}

export function useDepartments() {
  return useQuery({
    queryKey: teamKeys.departments,
    queryFn: async () => unwrap(await api.GET('/api/v1/team/departments')),
  });
}

export function useDesignations() {
  return useQuery({
    queryKey: teamKeys.designations,
    queryFn: async () => unwrap(await api.GET('/api/v1/team/designations')),
  });
}

/** Any people change can move the directory, profiles, history and headcounts. */
function useRefreshPeople() {
  const queryClient = useQueryClient();
  return (employee?: EmployeeDetail) => {
    if (employee) queryClient.setQueryData(teamKeys.employee(employee.id), employee);
    return queryClient.invalidateQueries({
      predicate: (query) =>
        query.queryKey[0] === 'team' &&
        !(employee && query.queryKey[1] === 'employee' && query.queryKey[2] === employee.id),
    });
  };
}

export function useCreateEmployee() {
  const refresh = useRefreshPeople();
  return useMutation({
    mutationFn: async (body: EmployeeCreate) =>
      unwrap(await api.POST('/api/v1/team/employees', { body })),
    onSuccess: (employee) => refresh(employee),
  });
}

export function useUpdateEmployee(id: string) {
  const refresh = useRefreshPeople();
  return useMutation({
    mutationFn: async (body: EmployeeUpdate) =>
      unwrap(
        await api.PATCH('/api/v1/team/employees/{employee_id}', {
          params: { path: { employee_id: id } },
          body,
        }),
      ),
    onSuccess: (employee) => refresh(employee),
  });
}

export function useUpdatePersonal(id: string) {
  const refresh = useRefreshPeople();
  return useMutation({
    mutationFn: async (body: PersonalUpdate) =>
      unwrap(
        await api.PATCH('/api/v1/team/employees/{employee_id}/personal', {
          params: { path: { employee_id: id } },
          body,
        }),
      ),
    onSuccess: (employee) => refresh(employee),
  });
}

export function useSaveDepartment() {
  const refresh = useRefreshPeople();
  return useMutation({
    mutationFn: async ({
      id,
      ...body
    }: {
      id?: string;
      name?: string;
      description?: string | null;
      head_id?: string | null;
      owner_ids?: string[];
      delivery_manager_id?: string | null;
      is_active?: boolean;
    }) =>
      id
        ? unwrap(
            await api.PATCH('/api/v1/team/departments/{department_id}', {
              params: { path: { department_id: id } },
              body,
            }),
          )
        : unwrap(
            await api.POST('/api/v1/team/departments', {
              body: { ...body, name: body.name ?? '' },
            }),
          ),
    onSuccess: () => refresh(),
  });
}

export function useSaveDesignation() {
  const refresh = useRefreshPeople();
  return useMutation({
    mutationFn: async ({
      id,
      ...body
    }: {
      id?: string;
      name?: string;
      department_id?: string | null;
      is_active?: boolean;
    }) =>
      id
        ? unwrap(
            await api.PATCH('/api/v1/team/designations/{designation_id}', {
              params: { path: { designation_id: id } },
              body,
            }),
          )
        : unwrap(
            await api.POST('/api/v1/team/designations', {
              body: { name: body.name ?? '', department_id: body.department_id ?? null },
            }),
          ),
    onSuccess: () => refresh(),
  });
}

// ---------------------------------------------------------------- Organization & Role Settings

export function useOrgChart(enabled = true) {
  return useQuery({
    queryKey: teamKeys.orgChart,
    queryFn: async () => unwrap(await api.GET('/api/v1/team/org-chart')),
    enabled,
  });
}

export function useReporting(id: string | null) {
  return useQuery({
    queryKey: teamKeys.reporting(id ?? ''),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/team/employees/{employee_id}/reporting', {
          params: { path: { employee_id: id ?? '' } },
        }),
      ),
    enabled: Boolean(id),
  });
}

export function usePreviewReporting(id: string) {
  return useMutation({
    mutationFn: async (body: ReportingChange) =>
      unwrap(
        await api.POST('/api/v1/team/employees/{employee_id}/reporting/preview', {
          params: { path: { employee_id: id } },
          body,
        }),
      ),
  });
}

export function useSaveReporting(id: string) {
  const refresh = useRefreshPeople();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: ReportingChange) =>
      unwrap(
        await api.PUT('/api/v1/team/employees/{employee_id}/reporting', {
          params: { path: { employee_id: id } },
          body,
        }),
      ),
    onSuccess: (reporting) => {
      queryClient.setQueryData(teamKeys.reporting(id), reporting);
      void refresh();
    },
  });
}

export function useProjectOptions(enabled: boolean) {
  return useQuery({
    queryKey: teamKeys.projectOptions,
    queryFn: async () => unwrap(await api.GET('/api/v1/team/project-options')),
    enabled,
  });
}

export function useRoles(enabled: boolean) {
  return useQuery({
    queryKey: teamKeys.roles,
    queryFn: async () => unwrap(await api.GET('/api/v1/team/roles')),
    enabled,
  });
}

export function useUserRoles(enabled: boolean) {
  return useQuery({
    queryKey: teamKeys.users,
    queryFn: async () => unwrap(await api.GET('/api/v1/team/users')),
    enabled,
  });
}

function useRefreshRoles() {
  const queryClient = useQueryClient();
  return () =>
    void queryClient.invalidateQueries({
      predicate: (q) =>
        q.queryKey[0] === 'team' && ['roles', 'users', 'org-audit'].includes(String(q.queryKey[1])),
    });
}

export function useSaveRole() {
  const refresh = useRefreshRoles();
  return useMutation({
    mutationFn: async ({
      create,
      key,
      name,
      description,
      permissions,
    }: {
      create: boolean;
      key: string;
      name: string;
      description?: string | null;
      permissions: string[];
    }) =>
      create
        ? unwrap(
            await api.POST('/api/v1/team/roles', {
              body: { key, name, description, permissions },
            }),
          )
        : unwrap(
            await api.PATCH('/api/v1/team/roles/{key}', {
              params: { path: { key } },
              body: { name, description, permissions },
            }),
          ),
    onSuccess: refresh,
  });
}

export function useSetUserRoles() {
  const refresh = useRefreshRoles();
  return useMutation({
    mutationFn: async ({ userId, roles }: { userId: string; roles: string[] }) =>
      unwrap(
        await api.PUT('/api/v1/team/users/{user_id}/roles', {
          params: { path: { user_id: userId } },
          body: { roles },
        }),
      ),
    onSuccess: refresh,
  });
}

export function useOrgAudit(enabled: boolean) {
  return useQuery({
    queryKey: teamKeys.audit,
    queryFn: async () => unwrap(await api.GET('/api/v1/team/org-audit')),
    enabled,
  });
}

// ---------------------------------------------------------------- Team & Roles: accounts

export type Account = components['schemas']['Account'];
export type AccountsOverview = components['schemas']['AccountsOverview'];
export type InviteRequest = components['schemas']['InviteRequest'];

export const accountsKey = ['team', 'accounts'] as const;

export function useAccounts() {
  return useQuery({
    queryKey: accountsKey,
    queryFn: async () => unwrap(await api.GET('/api/v1/team/accounts')),
  });
}

function useRefreshAccounts() {
  const queryClient = useQueryClient();
  return () =>
    void queryClient.invalidateQueries({
      predicate: (q) =>
        q.queryKey[0] === 'team' &&
        [
          'accounts',
          'users',
          'roles',
          'org-audit',
          'registrations',
          'employees',
          'employee',
        ].includes(String(q.queryKey[1])),
    });
}

export function useInvite() {
  const refresh = useRefreshAccounts();
  return useMutation({
    mutationFn: async (body: InviteRequest) =>
      unwrap(await api.POST('/api/v1/team/accounts/invite', { body })),
    onSuccess: refresh,
  });
}

export function useSetAccountActive() {
  const refresh = useRefreshAccounts();
  return useMutation({
    mutationFn: async ({ id, active }: { id: string; active: boolean }) =>
      unwrap(
        active
          ? await api.POST('/api/v1/team/accounts/{user_id}/reactivate', {
              params: { path: { user_id: id } },
            })
          : await api.POST('/api/v1/team/accounts/{user_id}/deactivate', {
              params: { path: { user_id: id } },
            }),
      ),
    onSuccess: refresh,
  });
}
