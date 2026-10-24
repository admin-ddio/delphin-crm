/** Typed TanStack Query hooks for the approvals module (types come from the generated schema). */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type { components } from '@/api/schema';
import type { BadgeTone } from '@/components/ui/Badge';
import { clientsKeys } from '@/features/clients/api';
import { tasksKeys, type TaskDetail } from '@/features/tasks/api';
import { api, unwrap } from '@/lib/api-client';

export type ApprovalItem = components['schemas']['ApprovalItem'];
export type DecisionIn = components['schemas']['DecisionIn'];
export type SubmitIn = components['schemas']['SubmitIn'];
export type Channel = NonNullable<DecisionIn['client_channel']>;
export type ApprovalView = 'mine' | 'all';

export const approvalsKeys = {
  all: ['approvals'] as const,
  list: (view: ApprovalView) => ['approvals', 'list', view] as const,
  detail: (id: string) => ['approvals', 'detail', id] as const,
};

export const APPROVAL_STATUS: Record<ApprovalItem['status'], { label: string; tone: BadgeTone }> = {
  submitted: { label: 'Awaiting decision', tone: 'accent' },
  approved: { label: 'Approved', tone: 'ok' },
  changes: { label: 'Changes requested', tone: 'warn' },
  cancelled: { label: 'Cancelled', tone: 'neutral' },
};

export const STAGE_LABEL: Record<ApprovalItem['stage'], string> = {
  internal: 'Internal',
  client: 'Client',
};

export const CHANNELS: { value: Channel; label: string }[] = [
  { value: 'email', label: 'Email' },
  { value: 'call', label: 'Call' },
  { value: 'meeting', label: 'Meeting' },
  { value: 'whatsapp', label: 'WhatsApp' },
];

export function useApprovals(view: ApprovalView) {
  return useQuery({
    queryKey: approvalsKeys.list(view),
    queryFn: async () =>
      unwrap(await api.GET('/api/v1/approvals', { params: { query: { view } } })),
  });
}

export function useApproval(id: string) {
  return useQuery({
    queryKey: approvalsKeys.detail(id),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/approvals/{approval_id}', {
          params: { path: { approval_id: id } },
        }),
      ),
  });
}

/** Submitting and deciding change the task, boards, approval lists and the client timeline. */
function useRefresh() {
  const queryClient = useQueryClient();
  return (task: TaskDetail) => {
    queryClient.setQueryData(tasksKeys.detail(task.id), task);
    return Promise.all([
      queryClient.invalidateQueries({ queryKey: approvalsKeys.all }),
      queryClient.invalidateQueries({ queryKey: ['tasks', 'list'] }),
      queryClient.invalidateQueries({ queryKey: ['projects'] }),
      queryClient.invalidateQueries({ queryKey: clientsKeys.activity(task.client_id) }),
    ]);
  };
}

export function useSubmitForReview() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: async (body: SubmitIn) =>
      unwrap(await api.POST('/api/v1/approvals/submit', { body })),
    onSuccess: refresh,
  });
}

export function useDecide(approvalId: string) {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: async (body: DecisionIn) =>
      unwrap(
        await api.POST('/api/v1/approvals/{approval_id}/decision', {
          params: { path: { approval_id: approvalId } },
          body,
        }),
      ),
    onSuccess: refresh,
  });
}
