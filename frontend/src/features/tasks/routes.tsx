import { groupByLayout } from '@/app/placeholder-route';
import { tasksRouteSpecs } from '@/features/tasks/route-specs';

export const routes = groupByLayout(tasksRouteSpecs, {
  '/tasks': () => import('@/features/tasks/TasksPage'),
  '/tasks/:id': () => import('@/features/tasks/TaskPage'),
});
