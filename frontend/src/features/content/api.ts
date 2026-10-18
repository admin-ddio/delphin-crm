/**
 * Typed TanStack Query hooks for the content module (stubs).
 *
 * Pattern once endpoints exist (types come from the generated schema, never by hand):
 *
 *   export function useContentList(params: ListParams) {
 *     return useQuery({
 *       queryKey: contentKeys.list(params),
 *       queryFn: async () => unwrap(await api.GET('/api/v1/content', { params: { query: params } })),
 *     });
 *   }
 */
export const contentKeys = {
  all: ['content'] as const,
  list: (params: Record<string, unknown> = {}) => ['content', 'list', params] as const,
  detail: (id: string) => ['content', 'detail', id] as const,
};
