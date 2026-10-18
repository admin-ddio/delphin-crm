/**
 * Typed TanStack Query hooks for the services module (stubs).
 *
 * Pattern once endpoints exist (types come from the generated schema, never by hand):
 *
 *   export function useServicesList(params: ListParams) {
 *     return useQuery({
 *       queryKey: servicesKeys.list(params),
 *       queryFn: async () => unwrap(await api.GET('/api/v1/services', { params: { query: params } })),
 *     });
 *   }
 */
export const servicesKeys = {
  all: ['services'] as const,
  list: (params: Record<string, unknown> = {}) => ['services', 'list', params] as const,
  detail: (id: string) => ['services', 'detail', id] as const,
};
