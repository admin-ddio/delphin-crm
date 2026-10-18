import type { RouteSpec } from '@/app/route-spec';

/** Pilot routes owned by the documents module. Titles are provisional (see RouteSpec.title). */
export const documentsRouteSpecs: readonly RouteSpec[] = [
  { path: '/documents', title: 'Documents', module: 'documents', layout: 'app' },
];
