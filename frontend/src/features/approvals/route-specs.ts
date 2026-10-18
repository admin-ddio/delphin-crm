import type { RouteSpec } from '@/app/route-spec';

/** Pilot routes owned by the approvals module. Titles are provisional (see RouteSpec.title). */
export const approvalsRouteSpecs: readonly RouteSpec[] = [
  { path: '/approvals', title: 'Approvals', module: 'approvals', layout: 'app', titleSource: 'demo' },
  { path: '/approvals/new', title: 'New approval', module: 'approvals', layout: 'app' },
  { path: '/approvals/:id', title: 'Approval', module: 'approvals', layout: 'app', screenshots: ['11-approval.png'] },
];
