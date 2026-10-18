/**
 * Typed TanStack Query hooks for the meetings module (stubs).
 *
 * Pattern once endpoints exist (types come from the generated schema, never by hand):
 *
 *   export function useMeetingsList(params: ListParams) {
 *     return useQuery({
 *       queryKey: meetingsKeys.list(params),
 *       queryFn: async () => unwrap(await api.GET('/api/v1/meetings', { params: { query: params } })),
 *     });
 *   }
 */
export const meetingsKeys = {
  all: ['meetings'] as const,
  list: (params: Record<string, unknown> = {}) => ['meetings', 'list', params] as const,
  detail: (id: string) => ['meetings', 'detail', id] as const,
};
