import type { RouteSpec } from '@/app/route-spec';

/** Pilot routes owned by the meetings module. Titles are provisional (see RouteSpec.title). */
export const meetingsRouteSpecs: readonly RouteSpec[] = [
  { path: '/meetings', title: 'Meetings', module: 'meetings', layout: 'app' },
  { path: '/meetings/new', title: 'New meeting', module: 'meetings', layout: 'app' },
  { path: '/meetings/:id', title: 'Meeting', module: 'meetings', layout: 'app' },
];
