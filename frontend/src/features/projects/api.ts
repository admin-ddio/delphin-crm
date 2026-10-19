/** Typed TanStack Query hooks for the projects module (types come from the generated schema). */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type { components } from '@/api/schema';
import { clientsKeys } from '@/features/clients/api';
import { onboardingKeys } from '@/features/onboarding/api';
import { api, unwrap } from '@/lib/api-client';

export type ProjectListItem = components['schemas']['ProjectListItem'];
export type ProjectDetail = components['schemas']['ProjectDetail'];
export type ProjectCreate = components['schemas']['ProjectCreate'];
export type EligibleClient = components['schemas']['EligibleClient'];

export const projectsKeys = {
  all: ['projects'] as const,
  list: (clientId?: string) => ['projects', 'list', clientId ?? null] as const,
  detail: (id: string) => ['projects', 'detail', id] as const,
  eligibleClients: ['projects', 'eligible-clients'] as const,
  managers: ['projects', 'manager-options'] as const,
};

export function useProjects(clientId?: string) {
  return useQuery({
    queryKey: projectsKeys.list(clientId),
    queryFn: async () =>
      unwrap(await api.GET('/api/v1/projects', { params: { query: { client_id: clientId } } })),
  });
}

export function useProject(id: string) {
  return useQuery({
    queryKey: projectsKeys.detail(id),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/projects/{project_id}', { params: { path: { project_id: id } } }),
      ),
  });
}

export function useEligibleClients(enabled = true) {
  return useQuery({
    queryKey: projectsKeys.eligibleClients,
    queryFn: async () => unwrap(await api.GET('/api/v1/projects/eligible-clients')),
    enabled,
  });
}

export function useManagerOptions(enabled = true) {
  return useQuery({
    queryKey: projectsKeys.managers,
    queryFn: async () => unwrap(await api.GET('/api/v1/projects/manager-options')),
    enabled,
    staleTime: 5 * 60_000,
  });
}

export function useCreateProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: ProjectCreate) => unwrap(await api.POST('/api/v1/projects', { body })),
    onSuccess: (project) => {
      queryClient.setQueryData(projectsKeys.detail(project.id), project);
      // The first project completes onboarding step 13.
      return Promise.all([
        queryClient.invalidateQueries({ queryKey: ['projects', 'list'] }),
        queryClient.invalidateQueries({ queryKey: projectsKeys.eligibleClients }),
        queryClient.invalidateQueries({ queryKey: ['tasks', 'list'] }),
        queryClient.invalidateQueries({ queryKey: onboardingKeys.board }),
        queryClient.invalidateQueries({ queryKey: onboardingKeys.detail(project.client_id) }),
        queryClient.invalidateQueries({ queryKey: clientsKeys.activity(project.client_id) }),
      ]);
    },
  });
}
