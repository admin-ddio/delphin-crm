/**
 * Typed TanStack Query hooks for the reports module (stubs).
 *
 * Pattern once endpoints exist (types come from the generated schema, never by hand):
 *
 *   export function useReportsList(params: ListParams) {
 *     return useQuery({
 *       queryKey: reportsKeys.list(params),
 *       queryFn: async () => unwrap(await api.GET('/api/v1/reports', { params: { query: params } })),
 *     });
 *   }
 */
export const reportsKeys = {
  all: ['reports'] as const,
  list: (params: Record<string, unknown> = {}) => ['reports', 'list', params] as const,
  detail: (id: string) => ['reports', 'detail', id] as const,
};
