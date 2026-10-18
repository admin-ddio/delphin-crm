import type { RouteSpec } from '@/app/route-spec';

/** Pilot routes owned by the content module. Titles are provisional (see RouteSpec.title). */
export const contentRouteSpecs: readonly RouteSpec[] = [
  { path: '/content', title: 'Content & Social', module: 'content', layout: 'app', screenshots: ['13-content.png'] },
  { path: '/content/new', title: 'New content', module: 'content', layout: 'app' },
  { path: '/content/:id', title: 'Content', module: 'content', layout: 'app' },
];
