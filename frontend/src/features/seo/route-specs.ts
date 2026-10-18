import type { RouteSpec } from '@/app/route-spec';

/** Pilot routes owned by the seo module. Titles are provisional (see RouteSpec.title). */
export const seoRouteSpecs: readonly RouteSpec[] = [
  { path: '/seo', title: 'SEO', module: 'seo', layout: 'app' },
  { path: '/seo/:clientId', title: 'SEO', module: 'seo', layout: 'app' },
];
