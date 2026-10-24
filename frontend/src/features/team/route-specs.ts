import type { RouteSpec } from '@/app/route-spec';

/** Pilot routes owned by the team module. Titles are provisional (see RouteSpec.title). */
export const teamRouteSpecs: readonly RouteSpec[] = [
  {
    path: '/team',
    title: 'Team & roles',
    module: 'team',
    layout: 'app',
    screenshots: ['16-team.png'],
    titleSource: 'demo',
    ported: true,
  },
  { path: '/team/employees', title: 'Employees', module: 'team', layout: 'app', ported: true },
  {
    path: '/team/employees/new',
    title: 'New employee',
    module: 'team',
    layout: 'app',
    ported: true,
  },
  { path: '/team/employees/:id', title: 'Employee', module: 'team', layout: 'app', ported: true },
  {
    path: '/team/teams',
    title: 'Organization & Role Settings',
    module: 'team',
    layout: 'app',
    ported: true,
  },
  { path: '/team/teams/:id', title: 'Team', module: 'team', layout: 'app' },
  { path: '/team/workload', title: 'Workload', module: 'team', layout: 'app' },
];
