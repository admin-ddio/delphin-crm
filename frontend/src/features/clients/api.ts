/**
 * Typed TanStack Query hooks for the clients module (stubs).
 *
 * Pattern once endpoints exist (types come from the generated schema, never by hand):
 *
 *   export function useClientsList(params: ListParams) {
 *     return useQuery({
 *       queryKey: clientsKeys.list(params),
 *       queryFn: async () => unwrap(await api.GET('/api/v1/clients', { params: { query: params } })),
 *     });
 *   }
 */
export const clientsKeys = {
  all: ['clients'] as const,
  list: (params: Record<string, unknown> = {}) => ['clients', 'list', params] as const,
  detail: (id: string) => ['clients', 'detail', id] as const,
};
