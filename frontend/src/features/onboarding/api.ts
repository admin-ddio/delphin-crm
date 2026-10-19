/** Typed TanStack Query hooks for the onboarding module. */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type { components } from '@/api/schema';
import { clientsKeys } from '@/features/clients/api';
import { api, unwrap } from '@/lib/api-client';

export type OnboardingDetail = components['schemas']['OnboardingDetail'];
export type BoardRow = components['schemas']['BoardRow'];
export type AccessItem = components['schemas']['AccessItemOut'];
export type AccessStatus = AccessItem['status'];
export type Step = components['schemas']['StepOut'];
export type KpiIn = components['schemas']['KpiIn'];
export type KickoffAction = components['schemas']['KickoffAction'];
export type ContactChannel = components['schemas']['KpiConfirmation']['via'];
export type PublicQuestionnaire = components['schemas']['PublicQuestionnaire'];

export const onboardingKeys = {
  board: ['onboarding', 'board'] as const,
  detail: (clientId: string) => ['onboarding', 'detail', clientId] as const,
  teamOptions: (clientId: string) => ['onboarding', 'team-options', clientId] as const,
  publicQuestionnaire: (token: string) => ['onboarding', 'public', token] as const,
};

const path = (clientId: string) => ({ params: { path: { client_id: clientId } } });

export function useOnboardingBoard() {
  return useQuery({
    queryKey: onboardingKeys.board,
    queryFn: async () => unwrap(await api.GET('/api/v1/onboarding')),
  });
}

export function useOnboarding(clientId: string) {
  return useQuery({
    queryKey: onboardingKeys.detail(clientId),
    queryFn: async () =>
      unwrap(await api.GET('/api/v1/onboarding/clients/{client_id}', path(clientId))),
  });
}

export function useTeamOptions(clientId: string, enabled: boolean) {
  return useQuery({
    queryKey: onboardingKeys.teamOptions(clientId),
    queryFn: async () =>
      unwrap(await api.GET('/api/v1/onboarding/clients/{client_id}/team/options', path(clientId))),
    enabled,
  });
}

/**
 * Every onboarding action returns the full OnboardingDetail: write it to the cache,
 * then refresh what it can change elsewhere (client status, activity, board, team).
 */
export function useOnboardingAction(clientId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (run: () => Promise<OnboardingDetail>) => run(),
    onSuccess: (detail) => {
      queryClient.setQueryData(onboardingKeys.detail(clientId), detail);
      return Promise.all([
        queryClient.invalidateQueries({ queryKey: clientsKeys.detail(clientId) }),
        queryClient.invalidateQueries({ queryKey: clientsKeys.activity(clientId) }),
        queryClient.invalidateQueries({ queryKey: ['clients', 'list'] }),
        queryClient.invalidateQueries({ queryKey: onboardingKeys.board }),
        queryClient.invalidateQueries({ queryKey: onboardingKeys.teamOptions(clientId) }),
      ]);
    },
  });
}

/** Typed calls used with useOnboardingAction (each returns OnboardingDetail). */
export const onboardingApi = {
  contract: async (clientId: string, action: 'record' | 'sign') =>
    unwrap(
      await api.POST('/api/v1/onboarding/clients/{client_id}/contract', {
        ...path(clientId),
        body: { action },
      }),
    ),
  sendQuestionnaire: async (clientId: string) =>
    unwrap(await api.POST('/api/v1/onboarding/clients/{client_id}/questionnaire/send', path(clientId))),
  recordAnswers: async (clientId: string, answers: Record<string, string>) =>
    unwrap(
      await api.POST('/api/v1/onboarding/clients/{client_id}/questionnaire/answers', {
        ...path(clientId),
        body: { answers },
      }),
    ),
  access: async (clientId: string, key: string, status: AccessStatus) =>
    unwrap(
      await api.PATCH('/api/v1/onboarding/clients/{client_id}/access/{key}', {
        params: { path: { client_id: clientId, key } },
        body: { status },
      }),
    ),
  receiveAll: async (clientId: string) =>
    unwrap(await api.POST('/api/v1/onboarding/clients/{client_id}/access/receive-all', path(clientId))),
  addKpi: async (clientId: string, body: KpiIn) =>
    unwrap(await api.POST('/api/v1/onboarding/clients/{client_id}/kpis', { ...path(clientId), body })),
  deleteKpi: async (clientId: string, kpiId: string) =>
    unwrap(
      await api.DELETE('/api/v1/onboarding/clients/{client_id}/kpis/{kpi_id}', {
        params: { path: { client_id: clientId, kpi_id: kpiId } },
      }),
    ),
  confirmKpis: async (clientId: string, confirmedBy: string, via: ContactChannel) =>
    unwrap(
      await api.POST('/api/v1/onboarding/clients/{client_id}/kpis/confirm', {
        ...path(clientId),
        body: { confirmed_by: confirmedBy, via },
      }),
    ),
  kickoff: async (clientId: string, kind: 'client' | 'internal', body: KickoffAction) =>
    unwrap(
      await api.POST('/api/v1/onboarding/clients/{client_id}/kickoffs/{kind}', {
        params: { path: { client_id: clientId, kind } },
        body,
      }),
    ),
  addTeamMember: async (clientId: string, userId: string) =>
    unwrap(
      await api.POST('/api/v1/onboarding/clients/{client_id}/team', {
        ...path(clientId),
        body: { user_id: userId },
      }),
    ),
  removeTeamMember: async (clientId: string, userId: string) =>
    unwrap(
      await api.DELETE('/api/v1/onboarding/clients/{client_id}/team/{user_id}', {
        params: { path: { client_id: clientId, user_id: userId } },
      }),
    ),
  review: async (clientId: string) =>
    unwrap(await api.POST('/api/v1/onboarding/clients/{client_id}/review', path(clientId))),
  complete: async (clientId: string) =>
    unwrap(await api.POST('/api/v1/onboarding/clients/{client_id}/complete', path(clientId))),
};

export function usePublicQuestionnaire(token: string) {
  return useQuery({
    queryKey: onboardingKeys.publicQuestionnaire(token),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/onboarding/questionnaire/{token}', {
          params: { path: { token } },
        }),
      ),
    retry: false,
  });
}

export async function submitPublicQuestionnaire(token: string, answers: Record<string, string>) {
  const { response, error } = await api.POST('/api/v1/onboarding/questionnaire/{token}', {
    params: { path: { token } },
    body: { answers },
  });
  if (!response.ok) unwrap({ error, response });
}
