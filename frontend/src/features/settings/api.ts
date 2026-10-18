/**
 * Typed TanStack Query hooks for the settings module (stubs).
 *
 * Pattern once endpoints exist (types come from the generated schema, never by hand):
 *
 *   export function useSettingsList(params: ListParams) {
 *     return useQuery({
 *       queryKey: settingsKeys.list(params),
 *       queryFn: async () => unwrap(await api.GET('/api/v1/settings', { params: { query: params } })),
 *     });
 *   }
 */
export const settingsKeys = {
  all: ['settings'] as const,
  list: (params: Record<string, unknown> = {}) => ['settings', 'list', params] as const,
  detail: (id: string) => ['settings', 'detail', id] as const,
};
