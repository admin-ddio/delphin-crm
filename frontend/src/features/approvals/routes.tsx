import { groupByLayout } from '@/app/placeholder-route';
import { approvalsRouteSpecs } from '@/features/approvals/route-specs';

export const routes = groupByLayout(approvalsRouteSpecs, {
  '/approvals': () => import('@/features/approvals/ApprovalsPage'),
  '/approvals/:id': () => import('@/features/approvals/ApprovalPage'),
});
