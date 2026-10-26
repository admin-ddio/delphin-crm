import type { RouteSpec } from '@/app/route-spec';

/** Pilot routes owned by the dashboard module. Titles are provisional (see RouteSpec.title). */
export const dashboardRouteSpecs: readonly RouteSpec[] = [
  {
    path: '/dashboard',
    title: 'Dashboard',
    module: 'dashboard',
    layout: 'app',
    screenshots: ['01-dashboard.png'],
    ported: true,
  },
];
