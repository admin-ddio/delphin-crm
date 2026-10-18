/**
 * Typed TanStack Query hooks for the team module (stubs).
 *
 * Pattern once endpoints exist (types come from the generated schema, never by hand):
 *
 *   export function useTeamList(params: ListParams) {
 *     return useQuery({
 *       queryKey: teamKeys.list(params),
 *       queryFn: async () => unwrap(await api.GET('/api/v1/team', { params: { query: params } })),
 *     });
 *   }
 */
export const teamKeys = {
  all: ['team'] as const,
  list: (params: Record<string, unknown> = {}) => ['team', 'list', params] as const,
  detail: (id: string) => ['team', 'detail', id] as const,
};
