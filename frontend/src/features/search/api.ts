/**
 * Typed TanStack Query hooks for the search module (stubs).
 *
 * Pattern once endpoints exist (types come from the generated schema, never by hand):
 *
 *   export function useSearchList(params: ListParams) {
 *     return useQuery({
 *       queryKey: searchKeys.list(params),
 *       queryFn: async () => unwrap(await api.GET('/api/v1/search', { params: { query: params } })),
 *     });
 *   }
 */
export const searchKeys = {
  all: ['search'] as const,
  list: (params: Record<string, unknown> = {}) => ['search', 'list', params] as const,
  detail: (id: string) => ['search', 'detail', id] as const,
};
