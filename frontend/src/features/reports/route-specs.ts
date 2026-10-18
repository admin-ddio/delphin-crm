import type { RouteSpec } from '@/app/route-spec';

/** Pilot routes owned by the reports module. Titles are provisional (see RouteSpec.title). */
export const reportsRouteSpecs: readonly RouteSpec[] = [
  { path: '/reports', title: 'Reports', module: 'reports', layout: 'app' },
];
