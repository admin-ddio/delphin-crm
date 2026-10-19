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

export interface DirectoryParams {
  q?: string;
  department_id?: string;
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

export function useDottedLines(id: string) {
  const refresh = useRefreshPeople();
  const add = useMutation({
    mutationFn: async (managerId: string) =>
      unwrap(
        await api.POST('/api/v1/team/employees/{employee_id}/dotted-lines', {
          params: { path: { employee_id: id } },
          body: { manager_id: managerId },
        }),
      ),
    onSuccess: (employee) => refresh(employee),
  });
  const end = useMutation({
    mutationFn: async (lineId: string) =>
      unwrap(
        await api.DELETE('/api/v1/team/employees/{employee_id}/dotted-lines/{line_id}', {
          params: { path: { employee_id: id, line_id: lineId } },
        }),
      ),
    onSuccess: (employee) => refresh(employee),
  });
  return { add, end };
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
              body: { name: body.name ?? '', description: body.description, head_id: body.head_id },
            }),
          ),
    onSuccess: () => refresh(),
  });
}

export function useSaveDesignation() {
  const refresh = useRefreshPeople();
  return useMutation({
    mutationFn: async ({ id, ...body }: { id?: string; name?: string; is_active?: boolean }) =>
      id
        ? unwrap(
            await api.PATCH('/api/v1/team/designations/{designation_id}', {
              params: { path: { designation_id: id } },
              body,
            }),
          )
        : unwrap(await api.POST('/api/v1/team/designations', { body: { name: body.name ?? '' } })),
    onSuccess: () => refresh(),
  });
}
