/**
 * Typed TanStack Query hooks for the dashboard module (stubs).
 *
 * Pattern once endpoints exist (types come from the generated schema, never by hand):
 *
 *   export function useDashboardList(params: ListParams) {
 *     return useQuery({
 *       queryKey: dashboardKeys.list(params),
 *       queryFn: async () => unwrap(await api.GET('/api/v1/dashboard', { params: { query: params } })),
 *     });
 *   }
 */
export const dashboardKeys = {
  all: ['dashboard'] as const,
  list: (params: Record<string, unknown> = {}) => ['dashboard', 'list', params] as const,
  detail: (id: string) => ['dashboard', 'detail', id] as const,
};
