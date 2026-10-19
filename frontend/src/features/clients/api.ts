/** Typed TanStack Query hooks for the clients module (types come from the generated schema). */
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type { components } from '@/api/schema';
import type { BadgeTone } from '@/components/ui/Badge';
import { api, unwrap } from '@/lib/api-client';

export type ClientListItem = components['schemas']['ClientListItem'];
export type ClientDetail = components['schemas']['ClientDetail'];
export type ClientCreate = components['schemas']['ClientCreate'];
export type ClientUpdate = components['schemas']['ClientUpdate'];
export type ClientStatus = ClientDetail['status'];
export type StatusCounts = components['schemas']['StatusCounts'];
export type AccountManagerOption = components['schemas']['AccountManagerOption'];
export type BusinessType = NonNullable<ClientCreate['business_type']>;
export type CompanySize = NonNullable<ClientCreate['company_size']>;
export type PaymentTerms = NonNullable<ClientCreate['payment_terms']>;

export interface ClientListParams {
  q?: string;
  status?: ClientStatus;
  page?: number;
  page_size?: number;
  sort?: string;
}

export const clientsKeys = {
  all: ['clients'] as const,
  list: (params: ClientListParams) => ['clients', 'list', params] as const,
  counts: ['clients', 'counts'] as const,
  detail: (id: string) => ['clients', 'detail', id] as const,
  activity: (id: string) => ['clients', 'activity', id] as const,
  accountManagers: ['clients', 'account-managers'] as const,
};

export const STATUS_OPTIONS: { value: ClientStatus; label: string }[] = [
  { value: 'onboarding', label: 'Onboarding' },
  { value: 'active', label: 'Active' },
  { value: 'on_hold', label: 'On Hold' },
  { value: 'completed', label: 'Completed' },
];

export const STATUS_TONE: Record<ClientStatus, BadgeTone> = {
  onboarding: 'warn',
  active: 'ok',
  on_hold: 'bad',
  completed: 'info',
};

export const BUSINESS_TYPES: { value: BusinessType; label: string }[] = [
  { value: 'b2b', label: 'B2B' },
  { value: 'b2c', label: 'B2C' },
  { value: 'b2b_b2c', label: 'B2B & B2C' },
  { value: 'd2c', label: 'D2C' },
  { value: 'non_profit', label: 'Non-profit' },
  { value: 'government', label: 'Government' },
];

export const COMPANY_SIZES: { value: CompanySize; label: string }[] = [
  { value: '1-10', label: '1 - 10 Employees' },
  { value: '11-50', label: '11 - 50 Employees' },
  { value: '51-200', label: '51 - 200 Employees' },
  { value: '201-500', label: '201 - 500 Employees' },
  { value: '501-1000', label: '501 - 1,000 Employees' },
  { value: '1000+', label: '1,000+ Employees' },
];

export const PAYMENT_TERMS: { value: PaymentTerms; label: string }[] = [
  { value: 'monthly', label: 'Monthly' },
  { value: 'quarterly', label: 'Quarterly' },
  { value: 'half_yearly', label: 'Half-yearly' },
  { value: 'annually', label: 'Annually' },
  { value: 'one_time', label: 'One-time' },
  { value: 'milestone', label: 'Milestone-based' },
];

export const INDUSTRIES = [
  'Information Technology',
  'E-commerce & Retail',
  'Healthcare',
  'Finance & Banking',
  'Real Estate',
  'Education',
  'Manufacturing',
  'Hospitality & Travel',
  'Professional Services',
  'Media & Entertainment',
  'Automotive',
  'Food & Beverage',
  'Non-profit',
  'Other',
];

export const labelOf = <T extends string>(
  options: readonly { value: T; label: string }[],
  value: T | null | undefined,
) => options.find((o) => o.value === value)?.label ?? null;

export function useClients(params: ClientListParams) {
  return useQuery({
    queryKey: clientsKeys.list(params),
    queryFn: async () => unwrap(await api.GET('/api/v1/clients', { params: { query: params } })),
    placeholderData: keepPreviousData,
  });
}

export function useClientCounts() {
  return useQuery({
    queryKey: clientsKeys.counts,
    queryFn: async () => unwrap(await api.GET('/api/v1/clients/counts')),
  });
}

export function useClient(id: string) {
  return useQuery({
    queryKey: clientsKeys.detail(id),
    queryFn: async () =>
      unwrap(await api.GET('/api/v1/clients/{client_id}', { params: { path: { client_id: id } } })),
  });
}

export function useClientActivity(id: string) {
  return useQuery({
    queryKey: clientsKeys.activity(id),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/clients/{client_id}/activity', {
          params: { path: { client_id: id } },
        }),
      ),
  });
}

export function useAccountManagers(enabled = true) {
  return useQuery({
    queryKey: clientsKeys.accountManagers,
    queryFn: async () => unwrap(await api.GET('/api/v1/clients/account-managers')),
    enabled,
    staleTime: 5 * 60_000,
  });
}

function useRefreshLists() {
  const queryClient = useQueryClient();
  return (client: ClientDetail) => {
    queryClient.setQueryData(clientsKeys.detail(client.id), client);
    return Promise.all([
      queryClient.invalidateQueries({ queryKey: ['clients', 'list'] }),
      queryClient.invalidateQueries({ queryKey: clientsKeys.counts }),
      queryClient.invalidateQueries({ queryKey: clientsKeys.activity(client.id) }),
      queryClient.invalidateQueries({ queryKey: ['onboarding'] }),
    ]);
  };
}

export function useCreateClient() {
  const refresh = useRefreshLists();
  return useMutation({
    mutationFn: async (body: ClientCreate) => unwrap(await api.POST('/api/v1/clients', { body })),
    onSuccess: refresh,
  });
}

export function useUpdateClient(id: string) {
  const refresh = useRefreshLists();
  return useMutation({
    mutationFn: async (body: ClientUpdate) =>
      unwrap(
        await api.PATCH('/api/v1/clients/{client_id}', {
          params: { path: { client_id: id } },
          body,
        }),
      ),
    onSuccess: refresh,
  });
}

export function useChangeClientStatus(id: string) {
  const refresh = useRefreshLists();
  return useMutation({
    mutationFn: async (action: 'hold' | 'complete' | 'reactivate') =>
      unwrap(
        await api.POST('/api/v1/clients/{client_id}/status', {
          params: { path: { client_id: id } },
          body: { action },
        }),
      ),
    onSuccess: refresh,
  });
}
