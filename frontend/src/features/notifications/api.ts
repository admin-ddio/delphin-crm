/** The signed-in user's notification bell. */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type { components } from '@/api/schema';
import { api, unwrap } from '@/lib/api-client';

export type NotificationList = components['schemas']['NotificationList'];

export const notificationsKey = ['notifications', 'mine'] as const;

export function useNotifications() {
  return useQuery({
    queryKey: notificationsKey,
    queryFn: async () => unwrap(await api.GET('/api/v1/notifications')),
    refetchInterval: 60_000,
  });
}

export function useMarkRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) =>
      id === 'all'
        ? unwrap(await api.POST('/api/v1/notifications/read-all'))
        : unwrap(
            await api.POST('/api/v1/notifications/{notification_id}/read', {
              params: { path: { notification_id: id } },
            }),
          ),
    onSuccess: (data) => queryClient.setQueryData(notificationsKey, data),
  });
}
