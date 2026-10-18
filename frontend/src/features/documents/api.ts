/**
 * Typed TanStack Query hooks for the documents module (stubs).
 *
 * Pattern once endpoints exist (types come from the generated schema, never by hand):
 *
 *   export function useDocumentsList(params: ListParams) {
 *     return useQuery({
 *       queryKey: documentsKeys.list(params),
 *       queryFn: async () => unwrap(await api.GET('/api/v1/documents', { params: { query: params } })),
 *     });
 *   }
 */
export const documentsKeys = {
  all: ['documents'] as const,
  list: (params: Record<string, unknown> = {}) => ['documents', 'list', params] as const,
  detail: (id: string) => ['documents', 'detail', id] as const,
};
