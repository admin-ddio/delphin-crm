import { useQuery } from '@tanstack/react-query';

import { api } from '@/lib/api-client';

/**
 * Bootstraps the API session on load: GET /api/v1/auth/csrf sets the double-submit
 * CSRF cookie every later mutation needs (see lib/api-client.ts), and its result
 * doubles as the "is the API reachable" signal.
 */
export function useApiConnection() {
  return useQuery({
    queryKey: ['api', 'connection'],
    queryFn: async () => {
      const { response } = await api.GET('/api/v1/auth/csrf');
      if (!response.ok) throw new Error(`API answered ${response.status}`);
      return true;
    },
    staleTime: Infinity,
    retry: 1,
  });
}
