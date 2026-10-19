import { groupByLayout } from '@/app/placeholder-route';
import { dashboardRouteSpecs } from '@/features/dashboard/route-specs';

export const routes = groupByLayout(dashboardRouteSpecs, {
  '/dashboard': () => import('@/features/dashboard/DashboardPage'),
});
