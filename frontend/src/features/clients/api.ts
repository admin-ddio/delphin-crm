/** Typed TanStack Query hooks for the clients module (types come from the generated schema). */
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type { components } from '@/api/schema';
import { api, unwrap } from '@/lib/api-client';

export type ClientListItem = components['schemas']['ClientListItem'];
export type ClientDetail = components['schemas']['ClientDetail'];
export type ClientCreate = components['schemas']['ClientCreate'];
export type ClientUpdate = components['schemas']['ClientUpdate'];
export type ClientStatus = ClientDetail['status'];
export type AccountManagerOption = components['schemas']['AccountManagerOption'];

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
  detail: (id: string) => ['clients', 'detail', id] as const,
  activity: (id: string) => ['clients', 'activity', id] as const,
  accountManagers: ['clients', 'account-managers'] as const,
};

export const STATUS_OPTIONS: { value: ClientStatus; label: string }[] = [
  { value: 'contract_pending', label: 'Contract pending' },
  { value: 'onboarding', label: 'Onboarding' },
  { value: 'active', label: 'Active' },
];

export function useClients(params: ClientListParams) {
  return useQuery({
    queryKey: clientsKeys.list(params),
    queryFn: async () => unwrap(await api.GET('/api/v1/clients', { params: { query: params } })),
    placeholderData: keepPreviousData,
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

export function useCreateClient() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: ClientCreate) =>
      unwrap(await api.POST('/api/v1/clients', { body })),
    onSuccess: (client) => {
      queryClient.setQueryData(clientsKeys.detail(client.id), client);
      return queryClient.invalidateQueries({ queryKey: ['clients', 'list'] });
    },
  });
}

export function useUpdateClient(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: ClientUpdate) =>
      unwrap(
        await api.PATCH('/api/v1/clients/{client_id}', {
          params: { path: { client_id: id } },
          body,
        }),
      ),
    onSuccess: (client) => {
      queryClient.setQueryData(clientsKeys.detail(id), client);
      return Promise.all([
        queryClient.invalidateQueries({ queryKey: ['clients', 'list'] }),
        queryClient.invalidateQueries({ queryKey: clientsKeys.activity(id) }),
      ]);
    },
  });
}
