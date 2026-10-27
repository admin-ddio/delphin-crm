import type { RouteSpec } from '@/app/route-spec';

/** Activity log: known from the clickable demo only (not in the scaffold brief's route list). */
export const activityRouteSpecs: readonly RouteSpec[] = [
  {
    path: '/activity',
    title: 'Activity log',
    module: 'activity',
    layout: 'app',
    titleSource: 'demo',
    ported: true,
  },
];
