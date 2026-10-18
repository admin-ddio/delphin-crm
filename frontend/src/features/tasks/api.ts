/**
 * Typed TanStack Query hooks for the tasks module (stubs).
 *
 * Pattern once endpoints exist (types come from the generated schema, never by hand):
 *
 *   export function useTasksList(params: ListParams) {
 *     return useQuery({
 *       queryKey: tasksKeys.list(params),
 *       queryFn: async () => unwrap(await api.GET('/api/v1/tasks', { params: { query: params } })),
 *     });
 *   }
 */
export const tasksKeys = {
  all: ['tasks'] as const,
  list: (params: Record<string, unknown> = {}) => ['tasks', 'list', params] as const,
  detail: (id: string) => ['tasks', 'detail', id] as const,
};
