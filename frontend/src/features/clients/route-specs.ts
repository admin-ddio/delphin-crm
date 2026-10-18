import type { RouteSpec } from '@/app/route-spec';

/** Pilot routes owned by the clients module. Titles are provisional (see RouteSpec.title). */
export const clientsRouteSpecs: readonly RouteSpec[] = [
  { path: '/clients', title: 'CRM & Clients', module: 'clients', layout: 'app', screenshots: ['02-clients.png'], titleSource: 'demo' },
  { path: '/clients/new', title: 'New client', module: 'clients', layout: 'app', titleSource: 'demo' },
  { path: '/clients/:id', title: 'Client overview', module: 'clients', layout: 'app', screenshots: ['03-client-overview.png'] },
  { path: '/clients/:id/edit', title: 'Edit client', module: 'clients', layout: 'app' },
  { path: '/clients/:id/contacts', title: 'Contacts', module: 'clients', layout: 'app' },
  { path: '/clients/:id/onboarding', title: 'Onboarding', module: 'clients', layout: 'app', screenshots: ['04-onboarding-summary.png', '05-onboarding-access.png', '06-onboarding-kpis.png', '07-onboarding-review.png'] },
  { path: '/clients/:id/projects', title: 'Projects', module: 'clients', layout: 'app' },
  { path: '/clients/:id/tasks', title: 'Tasks', module: 'clients', layout: 'app' },
  { path: '/clients/:id/services', title: 'Services', module: 'clients', layout: 'app' },
  { path: '/clients/:id/kpis', title: 'KPIs', module: 'clients', layout: 'app' },
  { path: '/clients/:id/meetings', title: 'Meetings', module: 'clients', layout: 'app' },
  { path: '/clients/:id/communications', title: 'Communications', module: 'clients', layout: 'app' },
  { path: '/clients/:id/documents', title: 'Documents', module: 'clients', layout: 'app' },
  { path: '/clients/:id/approvals', title: 'Approvals', module: 'clients', layout: 'app' },
  { path: '/clients/:id/billing', title: 'Billing', module: 'clients', layout: 'app' },
  { path: '/clients/:id/activity', title: 'Activity', module: 'clients', layout: 'app' },
];
