/** Typed TanStack Query hooks for the tasks module (types come from the generated schema). */
import { useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query';

import type { components } from '@/api/schema';
import type { BadgeTone } from '@/components/ui/Badge';
import { clientsKeys } from '@/features/clients/api';
import { api, unwrap } from '@/lib/api-client';

export type TaskItem = components['schemas']['TaskItem'];
export type TaskDetail = components['schemas']['TaskDetail'];
export type TaskStatus = TaskItem['status'];
export type TaskCreate = components['schemas']['TaskCreate'];
export type TaskUpdate = components['schemas']['TaskUpdate'];
export type TaskView = 'mine' | 'review' | 'all';

export const tasksKeys = {
  all: ['tasks'] as const,
  list: (view: TaskView, openOnly: boolean) => ['tasks', 'list', view, openOnly] as const,
  detail: (id: string) => ['tasks', 'detail', id] as const,
  assignees: ['tasks', 'assignee-options'] as const,
};

/** Demo labels and pill tones. */
export const TASK_STATUS: Record<TaskStatus, { label: string; tone: BadgeTone }> = {
  backlog: { label: 'Backlog', tone: 'neutral' },
  ready: { label: 'Ready', tone: 'accent' },
  in_progress: { label: 'In progress', tone: 'accent' },
  blocked: { label: 'Blocked', tone: 'bad' },
  internal_review: { label: 'Internal review', tone: 'info' },
  client_approval: { label: 'Client approval', tone: 'info' },
  completed: { label: 'Completed', tone: 'ok' },
  cancelled: { label: 'Cancelled', tone: 'neutral' },
};

/** Kanban columns (cancelled tasks are hidden from the board). */
export const BOARD_COLUMNS: readonly TaskStatus[] = [
  'backlog',
  'ready',
  'in_progress',
  'blocked',
  'internal_review',
  'client_approval',
  'completed',
];

export function useTasks(view: TaskView, openOnly = true) {
  return useQuery({
    queryKey: tasksKeys.list(view, openOnly),
    queryFn: async () =>
      unwrap(await api.GET('/api/v1/tasks', { params: { query: { view, open_only: openOnly } } })),
  });
}

export function useTask(id: string | null) {
  return useQuery({
    queryKey: tasksKeys.detail(id ?? ''),
    queryFn: async () =>
      unwrap(await api.GET('/api/v1/tasks/{task_id}', { params: { path: { task_id: id ?? '' } } })),
    enabled: Boolean(id),
  });
}

export function useAssigneeOptions(enabled = true) {
  return useQuery({
    queryKey: tasksKeys.assignees,
    queryFn: async () => unwrap(await api.GET('/api/v1/tasks/assignee-options')),
    enabled,
    staleTime: 5 * 60_000,
  });
}

/** A task change can move project stats, boards, lists and the client timeline. */
function refreshAfter(queryClient: QueryClient, task: TaskDetail) {
  queryClient.setQueryData(tasksKeys.detail(task.id), task);
  return Promise.all([
    queryClient.invalidateQueries({ queryKey: ['tasks', 'list'] }),
    queryClient.invalidateQueries({ queryKey: ['projects'] }),
    queryClient.invalidateQueries({ queryKey: clientsKeys.activity(task.client_id) }),
  ]);
}

export function useCreateTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: TaskCreate) => unwrap(await api.POST('/api/v1/tasks', { body })),
    onSuccess: (task) => refreshAfter(queryClient, task),
  });
}

export function useUpdateTask(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: TaskUpdate) =>
      unwrap(
        await api.PATCH('/api/v1/tasks/{task_id}', { params: { path: { task_id: id } }, body }),
      ),
    onSuccess: (task) => refreshAfter(queryClient, task),
  });
}

export function useMoveTask(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (status: TaskStatus) =>
      unwrap(
        await api.POST('/api/v1/tasks/{task_id}/status', {
          params: { path: { task_id: id } },
          body: { status },
        }),
      ),
    onSuccess: (task) => refreshAfter(queryClient, task),
  });
}
