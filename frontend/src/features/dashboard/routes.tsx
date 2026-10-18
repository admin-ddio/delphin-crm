import { groupByLayout } from '@/app/placeholder-route';
import { dashboardRouteSpecs } from '@/features/dashboard/route-specs';

/** Lazy placeholder routes; each feature port swaps a page in without touching the router. */
export const routes = groupByLayout(dashboardRouteSpecs);
