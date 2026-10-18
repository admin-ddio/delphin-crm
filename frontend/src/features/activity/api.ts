/**
 * Typed TanStack Query hooks for the activity module (stubs).
 *
 * Pattern once endpoints exist (types come from the generated schema, never by hand):
 *
 *   export function useActivityList(params: ListParams) {
 *     return useQuery({
 *       queryKey: activityKeys.list(params),
 *       queryFn: async () => unwrap(await api.GET('/api/v1/activity', { params: { query: params } })),
 *     });
 *   }
 */
export const activityKeys = {
  all: ['activity'] as const,
  list: (params: Record<string, unknown> = {}) => ['activity', 'list', params] as const,
  detail: (id: string) => ['activity', 'detail', id] as const,
};
