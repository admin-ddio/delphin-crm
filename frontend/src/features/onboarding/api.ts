/**
 * Typed TanStack Query hooks for the onboarding module (stubs).
 *
 * Pattern once endpoints exist (types come from the generated schema, never by hand):
 *
 *   export function useOnboardingList(params: ListParams) {
 *     return useQuery({
 *       queryKey: onboardingKeys.list(params),
 *       queryFn: async () => unwrap(await api.GET('/api/v1/onboarding', { params: { query: params } })),
 *     });
 *   }
 */
export const onboardingKeys = {
  all: ['onboarding'] as const,
  list: (params: Record<string, unknown> = {}) => ['onboarding', 'list', params] as const,
  detail: (id: string) => ['onboarding', 'detail', id] as const,
};
