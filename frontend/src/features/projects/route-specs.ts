import type { RouteSpec } from '@/app/route-spec';

/** Pilot routes owned by the projects module. Titles are provisional (see RouteSpec.title). */
export const projectsRouteSpecs: readonly RouteSpec[] = [
  { path: '/projects', title: 'Projects', module: 'projects', layout: 'app', titleSource: 'demo', ported: true },
  { path: '/projects/new', title: 'New project', module: 'projects', layout: 'app', titleSource: 'demo', ported: true },
  { path: '/projects/:id', title: 'Project', module: 'projects', layout: 'app', screenshots: ['08-project.png', '09-project-board.png'], ported: true },
];
