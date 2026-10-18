/**
 * Typed TanStack Query hooks for the notifications module (stubs).
 *
 * Pattern once endpoints exist (types come from the generated schema, never by hand):
 *
 *   export function useNotificationsList(params: ListParams) {
 *     return useQuery({
 *       queryKey: notificationsKeys.list(params),
 *       queryFn: async () => unwrap(await api.GET('/api/v1/notifications', { params: { query: params } })),
 *     });
 *   }
 */
export const notificationsKeys = {
  all: ['notifications'] as const,
  list: (params: Record<string, unknown> = {}) => ['notifications', 'list', params] as const,
  detail: (id: string) => ['notifications', 'detail', id] as const,
};
