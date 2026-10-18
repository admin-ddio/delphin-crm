import type { RouteSpec } from '@/app/route-spec';

/** Pilot routes owned by the services module. Titles are provisional (see RouteSpec.title). */
export const servicesRouteSpecs: readonly RouteSpec[] = [
  { path: '/services', title: 'Services & retainers', module: 'services', layout: 'app', titleSource: 'demo' },
  { path: '/services/:id', title: 'Service', module: 'services', layout: 'app' },
  { path: '/services/retainers', title: 'Retainers', module: 'services', layout: 'app' },
  { path: '/services/templates', title: 'Service templates', module: 'services', layout: 'app' },
  { path: '/services/workspace/:csId', title: 'Service workspace', module: 'services', layout: 'app', screenshots: ['12-retainer-workspace.png'] },
];
