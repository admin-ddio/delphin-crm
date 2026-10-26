import type { RouteSpec } from '@/app/route-spec';

/** Pilot routes owned by the settings module. Titles are provisional (see RouteSpec.title). */
export const settingsRouteSpecs: readonly RouteSpec[] = [
  { path: '/settings', title: 'Settings', module: 'settings', layout: 'app' },
  {
    path: '/settings/roles',
    title: 'Roles & permissions',
    module: 'settings',
    layout: 'app',
    screenshots: ['17-settings-roles.png'],
  },
  { path: '/settings/onboarding', title: 'Onboarding settings', module: 'settings', layout: 'app' },
  { path: '/settings/automation', title: 'Automation', module: 'settings', layout: 'app' },
  { path: '/settings/jobs', title: 'Jobs', module: 'settings', layout: 'app' },
  { path: '/settings/integrations', title: 'Integrations', module: 'settings', layout: 'app' },
  { path: '/settings/audit', title: 'Audit log', module: 'settings', layout: 'app' },
];
