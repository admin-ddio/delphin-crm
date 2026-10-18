import type { RouteSpec } from '@/app/route-spec';

/** Pilot routes owned by the search module. Titles are provisional (see RouteSpec.title). */
export const searchRouteSpecs: readonly RouteSpec[] = [
  { path: '/search', title: 'Search', module: 'search', layout: 'app' },
];
