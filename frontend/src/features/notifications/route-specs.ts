import type { RouteSpec } from '@/app/route-spec';

/** Pilot routes owned by the notifications module. Titles are provisional (see RouteSpec.title). */
export const notificationsRouteSpecs: readonly RouteSpec[] = [
  { path: '/notifications', title: 'Notifications', module: 'notifications', layout: 'app' },
];
