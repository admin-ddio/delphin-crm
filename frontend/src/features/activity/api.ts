/** Typed TanStack Query hooks for the activity log (types from the generated schema). */
import { useInfiniteQuery } from '@tanstack/react-query';

import type { components } from '@/api/schema';
import { api, unwrap } from '@/lib/api-client';

export type ActivityItem = components['schemas']['ActivityItem'];
export type ActivityArea = ActivityItem['area'];

export interface ActivityFilters {
  client_id?: string;
  person_id?: string;
  area?: ActivityArea;
  since?: string;
  until?: string;
}

export const activityKeys = {
  all: ['activity'] as const,
  list: (filters: ActivityFilters = {}) => ['activity', 'list', filters] as const,
};

export const AREA_LABELS: Record<ActivityArea, string> = {
  clients: 'Clients',
  onboarding: 'Onboarding',
  projects: 'Projects & tasks',
  approvals: 'Approvals',
  documents: 'Documents',
  meetings: 'Meetings',
  services: 'Services',
  other: 'Other',
};

export function useActivity(filters: ActivityFilters) {
  return useInfiniteQuery({
    queryKey: activityKeys.list(filters),
    initialPageParam: undefined as string | undefined,
    queryFn: async ({ pageParam }) =>
      unwrap(
        await api.GET('/api/v1/activity', {
          params: { query: { ...filters, before: pageParam, limit: 50 } },
        }),
      ),
    getNextPageParam: (last) => last.next_before ?? undefined,
  });
}
