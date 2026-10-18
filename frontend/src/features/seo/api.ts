/**
 * Typed TanStack Query hooks for the seo module (stubs).
 *
 * Pattern once endpoints exist (types come from the generated schema, never by hand):
 *
 *   export function useSeoList(params: ListParams) {
 *     return useQuery({
 *       queryKey: seoKeys.list(params),
 *       queryFn: async () => unwrap(await api.GET('/api/v1/seo', { params: { query: params } })),
 *     });
 *   }
 */
export const seoKeys = {
  all: ['seo'] as const,
  list: (params: Record<string, unknown> = {}) => ['seo', 'list', params] as const,
  detail: (id: string) => ['seo', 'detail', id] as const,
};
