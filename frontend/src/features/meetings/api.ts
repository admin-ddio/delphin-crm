/** Typed TanStack Query hooks for meetings (types come from the generated schema). */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type { components } from '@/api/schema';
import type { BadgeTone } from '@/components/ui/Badge';
import { clientsKeys } from '@/features/clients/api';
import { onboardingKeys } from '@/features/onboarding/api';
import { api, unwrap } from '@/lib/api-client';

export type Meeting = components['schemas']['MeetingOut'];
export type MeetingIn = components['schemas']['MeetingIn'];
export type MeetingUpdate = components['schemas']['MeetingUpdate'];
export type MeetingType = Meeting['type'];
export type Platform = NonNullable<Meeting['platform']>;
export type ClientMeetings = components['schemas']['ClientMeetings'];

export const meetingsKeys = {
  client: (clientId: string) => ['meetings', 'client', clientId] as const,
};

export const MEETING_TYPES: { value: MeetingType; label: string; tone: BadgeTone }[] = [
  { value: 'kickoff', label: 'Kickoff', tone: 'accent' },
  { value: 'review', label: 'Review', tone: 'warn' },
  { value: 'planning', label: 'Planning', tone: 'bad' },
  { value: 'internal', label: 'Internal', tone: 'neutral' },
  { value: 'reporting', label: 'Reporting', tone: 'info' },
  { value: 'other', label: 'Other', tone: 'neutral' },
];

export const PLATFORMS: { value: Platform; label: string }[] = [
  { value: 'google_meet', label: 'Google Meet' },
  { value: 'zoom', label: 'Zoom' },
  { value: 'teams', label: 'Microsoft Teams' },
  { value: 'phone', label: 'Phone call' },
  { value: 'in_person', label: 'In person' },
  { value: 'other', label: 'Other' },
];

export const MEETING_STATUS: Record<Meeting['display_status'], { label: string; tone: BadgeTone }> =
  {
    upcoming: { label: 'Upcoming', tone: 'info' },
    awaiting_notes: { label: 'Awaiting notes', tone: 'warn' },
    completed: { label: 'Completed', tone: 'ok' },
    cancelled: { label: 'Cancelled', tone: 'neutral' },
  };

export function useClientMeetings(clientId: string) {
  return useQuery({
    queryKey: meetingsKeys.client(clientId),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/meetings/clients/{client_id}', {
          params: { path: { client_id: clientId } },
        }),
      ),
  });
}

/** Meeting changes can complete kickoff steps: refresh onboarding and the timeline too. */
export function useMeetingAction(clientId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (run: () => Promise<Meeting>) => run(),
    onSuccess: () => {
      void Promise.all([
        queryClient.invalidateQueries({ queryKey: meetingsKeys.client(clientId) }),
        queryClient.invalidateQueries({ queryKey: onboardingKeys.detail(clientId) }),
        queryClient.invalidateQueries({ queryKey: onboardingKeys.board }),
        queryClient.invalidateQueries({ queryKey: clientsKeys.activity(clientId) }),
      ]);
    },
  });
}

const meetingPath = (id: string) => ({ params: { path: { meeting_id: id } } });

export const meetingsApi = {
  schedule: async (body: MeetingIn) => unwrap(await api.POST('/api/v1/meetings', { body })),
  update: async (id: string, body: MeetingUpdate) =>
    unwrap(await api.PATCH('/api/v1/meetings/{meeting_id}', { ...meetingPath(id), body })),
  complete: async (id: string, notes: string) =>
    unwrap(
      await api.POST('/api/v1/meetings/{meeting_id}/complete', {
        ...meetingPath(id),
        body: { notes },
      }),
    ),
  cancel: async (id: string, reason: string | null) =>
    unwrap(
      await api.POST('/api/v1/meetings/{meeting_id}/cancel', {
        ...meetingPath(id),
        body: { reason },
      }),
    ),
  addActionItem: async (id: string, body: components['schemas']['ActionItemIn']) =>
    unwrap(
      await api.POST('/api/v1/meetings/{meeting_id}/action-items', { ...meetingPath(id), body }),
    ),
  updateActionItem: async (itemId: string, body: components['schemas']['ActionItemUpdate']) =>
    unwrap(
      await api.PATCH('/api/v1/meetings/action-items/{item_id}', {
        params: { path: { item_id: itemId } },
        body,
      }),
    ),
  deleteActionItem: async (itemId: string) =>
    unwrap(
      await api.DELETE('/api/v1/meetings/action-items/{item_id}', {
        params: { path: { item_id: itemId } },
      }),
    ),
};
