/**
 * Typed TanStack Query hooks for the auth module (stubs).
 *
 * Pattern once endpoints exist (types come from the generated schema, never by hand):
 *
 *   export function useAuthList(params: ListParams) {
 *     return useQuery({
 *       queryKey: authKeys.list(params),
 *       queryFn: async () => unwrap(await api.GET('/api/v1/auth', { params: { query: params } })),
 *     });
 *   }
 */
export const authKeys = {
  all: ['auth'] as const,
  list: (params: Record<string, unknown> = {}) => ['auth', 'list', params] as const,
  detail: (id: string) => ['auth', 'detail', id] as const,
};
