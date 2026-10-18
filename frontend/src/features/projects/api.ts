/**
 * Typed TanStack Query hooks for the projects module (stubs).
 *
 * Pattern once endpoints exist (types come from the generated schema, never by hand):
 *
 *   export function useProjectsList(params: ListParams) {
 *     return useQuery({
 *       queryKey: projectsKeys.list(params),
 *       queryFn: async () => unwrap(await api.GET('/api/v1/projects', { params: { query: params } })),
 *     });
 *   }
 */
export const projectsKeys = {
  all: ['projects'] as const,
  list: (params: Record<string, unknown> = {}) => ['projects', 'list', params] as const,
  detail: (id: string) => ['projects', 'detail', id] as const,
};
