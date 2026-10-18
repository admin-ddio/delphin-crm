import { QueryClient } from '@tanstack/react-query';

import { ApiError } from '@/lib/api-client';

const NO_RETRY_BELOW = 500;

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        refetchOnWindowFocus: false,
        // Client errors (401/403/404/422) are answers, not transient failures.
        retry: (failureCount, error) =>
          !(error instanceof ApiError && error.status < NO_RETRY_BELOW) && failureCount < 2,
      },
      mutations: { retry: false },
    },
  });
}
