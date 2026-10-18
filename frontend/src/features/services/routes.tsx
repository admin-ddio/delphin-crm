import { groupByLayout } from '@/app/placeholder-route';
import { servicesRouteSpecs } from '@/features/services/route-specs';

/** Lazy placeholder routes; each feature port swaps a page in without touching the router. */
export const routes = groupByLayout(servicesRouteSpecs);
