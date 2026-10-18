/**
 * Typed TanStack Query hooks for the approvals module (stubs).
 *
 * Pattern once endpoints exist (types come from the generated schema, never by hand):
 *
 *   export function useApprovalsList(params: ListParams) {
 *     return useQuery({
 *       queryKey: approvalsKeys.list(params),
 *       queryFn: async () => unwrap(await api.GET('/api/v1/approvals', { params: { query: params } })),
 *     });
 *   }
 */
export const approvalsKeys = {
  all: ['approvals'] as const,
  list: (params: Record<string, unknown> = {}) => ['approvals', 'list', params] as const,
  detail: (id: string) => ['approvals', 'detail', id] as const,
};
