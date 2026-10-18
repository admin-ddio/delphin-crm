/**
 * Typed TanStack Query hooks for the finance module (stubs).
 *
 * Pattern once endpoints exist (types come from the generated schema, never by hand):
 *
 *   export function useFinanceList(params: ListParams) {
 *     return useQuery({
 *       queryKey: financeKeys.list(params),
 *       queryFn: async () => unwrap(await api.GET('/api/v1/finance', { params: { query: params } })),
 *     });
 *   }
 */
export const financeKeys = {
  all: ['finance'] as const,
  list: (params: Record<string, unknown> = {}) => ['finance', 'list', params] as const,
  detail: (id: string) => ['finance', 'detail', id] as const,
};
