import type { RouteSpec } from '@/app/route-spec';

/** Pilot routes owned by the tasks module. Titles are provisional (see RouteSpec.title). */
export const tasksRouteSpecs: readonly RouteSpec[] = [
  {
    path: '/tasks',
    title: 'Tasks & work',
    module: 'tasks',
    layout: 'app',
    titleSource: 'demo',
    ported: true,
  },
  { path: '/tasks/new', title: 'New task', module: 'tasks', layout: 'app' },
  {
    path: '/tasks/:id',
    title: 'Task',
    module: 'tasks',
    layout: 'app',
    screenshots: ['10-task.png'],
    ported: true,
  },
];
