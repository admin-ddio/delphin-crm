/** Typed TanStack Query hooks for the onboarding module (v2). */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type { components } from '@/api/schema';
import type { BadgeTone } from '@/components/ui/Badge';
import { clientsKeys } from '@/features/clients/api';
import { api, unwrap } from '@/lib/api-client';

export type OnboardingDetail = components['schemas']['OnboardingDetail'];
export type BoardRow = components['schemas']['BoardRow'];
export type AccessItem = components['schemas']['AccessItemOut'];
export type AccessStatus = AccessItem['status'];
export type Step = components['schemas']['StepOut'];
export type Stage = components['schemas']['StageOut'];
export type Kpi = components['schemas']['KpiOut'];
export type KpiIn = components['schemas']['KpiIn'];
export type KpiUpdate = components['schemas']['KpiUpdate'];
export type KpiStatus = Kpi['status'];
export type ContactChannel = components['schemas']['KpiConfirmation']['via'];
export type Answers = components['schemas']['Answers'];
/** What the wizard needs; shared by the staff (QuestionnaireOut) and public views. */
export type QuestionnaireForm = Pick<
  components['schemas']['QuestionnaireOut'],
  'sections' | 'goals' | 'tones' | 'answers'
>;
export type PublicQuestionnaire = components['schemas']['PublicQuestionnaire'];
export type TeamMember = components['schemas']['TeamMemberOut'];
export type TeamMemberIn = components['schemas']['TeamMemberIn'];
export type TeamArea = NonNullable<TeamMember['area']>;

export const onboardingKeys = {
  board: ['onboarding', 'board'] as const,
  detail: (clientId: string) => ['onboarding', 'detail', clientId] as const,
  teamOptions: (clientId: string) => ['onboarding', 'team-options', clientId] as const,
  publicQuestionnaire: (token: string) => ['onboarding', 'public', token] as const,
};

export const ONBOARDING_STATUS: Record<BoardRow['status'], { label: string; tone: BadgeTone }> = {
  in_progress: { label: 'In progress', tone: 'accent' },
  blocked: { label: 'Blocked', tone: 'bad' },
  completed: { label: 'Completed', tone: 'ok' },
};

export const STAGE_STATE: Record<Stage['state'], { label: string; tone: BadgeTone }> = {
  completed: { label: 'Completed', tone: 'ok' },
  in_progress: { label: 'In Progress', tone: 'warn' },
  pending: { label: 'Pending', tone: 'neutral' },
  blocked: { label: 'Blocked', tone: 'bad' },
};

export const ACCESS_STATUS: Record<AccessStatus, { label: string; tone: BadgeTone }> = {
  pending: { label: 'Pending', tone: 'neutral' },
  requested: { label: 'Requested', tone: 'warn' },
  received: { label: 'Received', tone: 'warn' },
  verified: { label: 'Verified', tone: 'ok' },
  rejected: { label: 'Rejected', tone: 'bad' },
  not_required: { label: 'Not required', tone: 'neutral' },
};

export const KPI_STATUS: Record<KpiStatus, { label: string; tone: BadgeTone }> = {
  on_track: { label: 'On Track', tone: 'ok' },
  at_risk: { label: 'At Risk', tone: 'warn' },
  behind: { label: 'Behind', tone: 'bad' },
  achieved: { label: 'Achieved', tone: 'ok' },
  not_measured: { label: 'Not measured', tone: 'neutral' },
};

export const CHANNELS: { value: ContactChannel; label: string }[] = [
  { value: 'email', label: 'Email' },
  { value: 'call', label: 'Call' },
  { value: 'meeting', label: 'Meeting' },
  { value: 'whatsapp', label: 'WhatsApp' },
];

export const AREAS: { value: TeamArea; label: string }[] = [
  { value: 'account', label: 'Account management' },
  { value: 'project_management', label: 'Project management' },
  { value: 'seo', label: 'SEO' },
  { value: 'content', label: 'Content' },
  { value: 'design', label: 'Design' },
  { value: 'development', label: 'Development' },
  { value: 'social', label: 'Social media' },
  { value: 'analytics', label: 'Analytics & reporting' },
];

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
 * then refresh what it can change elsewhere (client status, activity, lists).
 */
export function useOnboardingAction(clientId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (run: () => Promise<OnboardingDetail>) => run(),
    onSuccess: (detail) => {
      queryClient.setQueryData(onboardingKeys.detail(clientId), detail);
      // Refresh the rest in the background so dialogs close as soon as the action succeeds.
      void Promise.all([
        queryClient.invalidateQueries({ queryKey: clientsKeys.detail(clientId) }),
        queryClient.invalidateQueries({ queryKey: clientsKeys.activity(clientId) }),
        queryClient.invalidateQueries({ queryKey: ['clients', 'list'] }),
        queryClient.invalidateQueries({ queryKey: clientsKeys.counts }),
        queryClient.invalidateQueries({ queryKey: onboardingKeys.board }),
        queryClient.invalidateQueries({ queryKey: onboardingKeys.teamOptions(clientId) }),
      ]);
    },
  });
}

/** Typed calls used with useOnboardingAction (each returns OnboardingDetail). */
export const onboardingApi = {
  saveDraft: async (clientId: string, answers: Answers) =>
    unwrap(
      await api.PUT('/api/v1/onboarding/clients/{client_id}/questionnaire', {
        ...path(clientId),
        body: { answers },
      }),
    ),
  submitAnswers: async (clientId: string, answers: Answers) =>
    unwrap(
      await api.POST('/api/v1/onboarding/clients/{client_id}/questionnaire/submit', {
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
  bulkAccess: async (clientId: string, status: 'requested' | 'received') =>
    unwrap(
      await api.POST('/api/v1/onboarding/clients/{client_id}/access/bulk', {
        ...path(clientId),
        body: { status },
      }),
    ),
  addAccess: async (clientId: string, label: string, description: string | null) =>
    unwrap(
      await api.POST('/api/v1/onboarding/clients/{client_id}/access', {
        ...path(clientId),
        body: { label, description },
      }),
    ),
  accessNotes: async (clientId: string, key: string, notes: string | null) =>
    unwrap(
      await api.PATCH('/api/v1/onboarding/clients/{client_id}/access/{key}/details', {
        params: { path: { client_id: clientId, key } },
        body: { notes },
      }),
    ),
  deleteAccess: async (clientId: string, key: string) =>
    unwrap(
      await api.DELETE('/api/v1/onboarding/clients/{client_id}/access/{key}', {
        params: { path: { client_id: clientId, key } },
      }),
    ),
  addKpi: async (clientId: string, body: KpiIn) =>
    unwrap(
      await api.POST('/api/v1/onboarding/clients/{client_id}/kpis', { ...path(clientId), body }),
    ),
  updateKpi: async (clientId: string, kpiId: string, body: KpiUpdate) =>
    unwrap(
      await api.PATCH('/api/v1/onboarding/clients/{client_id}/kpis/{kpi_id}', {
        params: { path: { client_id: clientId, kpi_id: kpiId } },
        body,
      }),
    ),
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
  kpiNotes: async (clientId: string, notes: string | null) =>
    unwrap(
      await api.PUT('/api/v1/onboarding/clients/{client_id}/kpi-notes', {
        ...path(clientId),
        body: { notes },
      }),
    ),
  addTeamMember: async (clientId: string, body: TeamMemberIn) =>
    unwrap(
      await api.POST('/api/v1/onboarding/clients/{client_id}/team', { ...path(clientId), body }),
    ),
  updateTeamMember: async (
    clientId: string,
    userId: string,
    body: components['schemas']['TeamMemberUpdate'],
  ) =>
    unwrap(
      await api.PATCH('/api/v1/onboarding/clients/{client_id}/team/{user_id}', {
        params: { path: { client_id: clientId, user_id: userId } },
        body,
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

export async function sendQuestionnaire(clientId: string) {
  return unwrap(
    await api.POST('/api/v1/onboarding/clients/{client_id}/questionnaire/send', path(clientId)),
  );
}

export function usePublicQuestionnaire(token: string) {
  return useQuery({
    queryKey: onboardingKeys.publicQuestionnaire(token),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/onboarding/questionnaire/{token}', { params: { path: { token } } }),
      ),
    retry: false,
  });
}

export async function savePublicDraft(token: string, answers: Answers) {
  return unwrap(
    await api.PUT('/api/v1/onboarding/questionnaire/{token}', {
      params: { path: { token } },
      body: { answers },
    }),
  );
}

export async function submitPublicQuestionnaire(token: string, answers: Answers) {
  const { response, error } = await api.POST('/api/v1/onboarding/questionnaire/{token}', {
    params: { path: { token } },
    body: { answers },
  });
  if (!response.ok) unwrap({ error, response });
}
