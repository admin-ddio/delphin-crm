/** Typed TanStack Query hooks for services and retainers (types from the generated schema). */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type { components } from '@/api/schema';
import type { BadgeTone } from '@/components/ui/Badge';
import { api, unwrap } from '@/lib/api-client';

export type ServiceType = components['schemas']['ServiceTypeOut'];
export type ServiceItem = components['schemas']['ServiceItem'];
export type ServiceDetail = components['schemas']['ServiceDetail'];
export type ServicesOverview = components['schemas']['ServicesOverview'];
export type ServiceSelection = components['schemas']['ServiceSelection'];
export type ServiceStatus = ServiceItem['status'];
export type ServiceKind = ServiceItem['service']['kind'];
export type TemplateTask = components['schemas']['TemplateTaskOut'];
export type TemplateTaskIn = components['schemas']['TemplateTaskIn'];
export type StartOptions = components['schemas']['StartOptions'];

export interface ServicesParams {
  kind?: ServiceKind;
  status?: ServiceStatus;
  client_id?: string;
}

export const servicesKeys = {
  all: ['services'] as const,
  types: ['services', 'types'] as const,
  list: (params: ServicesParams = {}) => ['services', 'list', params] as const,
  detail: (id: string) => ['services', 'detail', id] as const,
  startOptions: (id: string) => ['services', 'start-options', id] as const,
  templates: (key: string) => ['services', 'templates', key] as const,
};

export const SERVICE_STATUS: Record<ServiceStatus, { label: string; tone: BadgeTone }> = {
  planned: { label: 'Planned', tone: 'info' },
  active: { label: 'Active', tone: 'ok' },
  paused: { label: 'Paused', tone: 'warn' },
  completed: { label: 'Completed', tone: 'neutral' },
  cancelled: { label: 'Cancelled', tone: 'neutral' },
};

export const AREA_LABELS: Record<string, string> = {
  account: 'Account management',
  project_management: 'Project management',
  seo: 'SEO',
  content: 'Content',
  design: 'Design',
  development: 'Development',
  social: 'Social media',
  analytics: 'Analytics',
};

export function formatMoney(value: string | null | undefined, currency = 'INR') {
  if (value === null || value === undefined) return null;
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency,
    maximumFractionDigits: 0,
  }).format(Number(value));
}

export function useServiceTypes() {
  return useQuery({
    queryKey: servicesKeys.types,
    queryFn: async () => unwrap(await api.GET('/api/v1/services/types')),
    staleTime: 5 * 60_000,
  });
}

export function useServices(params: ServicesParams = {}, enabled = true) {
  return useQuery({
    queryKey: servicesKeys.list(params),
    queryFn: async () => unwrap(await api.GET('/api/v1/services', { params: { query: params } })),
    enabled,
  });
}

export function useService(id: string) {
  return useQuery({
    queryKey: servicesKeys.detail(id),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/services/{service_id}', {
          params: { path: { service_id: id } },
        }),
      ),
  });
}

export function useStartOptions(id: string | null) {
  return useQuery({
    queryKey: servicesKeys.startOptions(id ?? ''),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/services/{service_id}/start-options', {
          params: { path: { service_id: id ?? '' } },
        }),
      ),
    enabled: Boolean(id),
  });
}

/** Service changes move lists, the workspace, projects, tasks and the client's onboarding. */
function useRefresh() {
  const queryClient = useQueryClient();
  return (detail?: ServiceDetail) => {
    if (detail) queryClient.setQueryData(servicesKeys.detail(detail.id), detail);
    void queryClient.invalidateQueries({
      predicate: (q) =>
        ['services', 'projects', 'tasks', 'onboarding', 'clients'].includes(
          String(q.queryKey[0]),
        ) && !(detail && q.queryKey[1] === 'detail' && q.queryKey[2] === detail.id),
    });
  };
}

export function useAddServices(clientId: string) {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: async (services: ServiceSelection[]) =>
      unwrap(
        await api.POST('/api/v1/services/clients/{client_id}', {
          params: { path: { client_id: clientId } },
          body: { services },
        }),
      ),
    onSuccess: () => refresh(),
  });
}

export function useStartService(id: string) {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: async (body: { manager_id: string; start_date: string }) =>
      unwrap(
        await api.POST('/api/v1/services/{service_id}/start', {
          params: { path: { service_id: id } },
          body,
        }),
      ),
    onSuccess: (detail) => refresh(detail),
  });
}

export type ServiceAction = 'pause' | 'resume' | 'complete' | 'cancel';

export function useServiceAction(id: string) {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: async (action: ServiceAction) => {
      const params = { params: { path: { service_id: id } } };
      const result =
        action === 'pause'
          ? await api.POST('/api/v1/services/{service_id}/pause', params)
          : action === 'resume'
            ? await api.POST('/api/v1/services/{service_id}/resume', params)
            : action === 'complete'
              ? await api.POST('/api/v1/services/{service_id}/complete', params)
              : await api.POST('/api/v1/services/{service_id}/cancel', params);
      return unwrap(result);
    },
    onSuccess: (detail) => refresh(detail),
  });
}

export function useGenerateMonth(id: string) {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST('/api/v1/services/{service_id}/generate', {
          params: { path: { service_id: id } },
        }),
      ),
    onSuccess: () => refresh(),
  });
}

export function useTemplates(key: string | null) {
  return useQuery({
    queryKey: servicesKeys.templates(key ?? ''),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/services/types/{key}/templates', {
          params: { path: { key: key ?? '' } },
        }),
      ),
    enabled: Boolean(key),
  });
}

export function useSaveTemplates(key: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (tasks: TemplateTaskIn[]) =>
      unwrap(
        await api.PUT('/api/v1/services/types/{key}/templates', {
          params: { path: { key } },
          body: { tasks },
        }),
      ),
    onSuccess: (saved) => queryClient.setQueryData(servicesKeys.templates(key), saved),
  });
}
