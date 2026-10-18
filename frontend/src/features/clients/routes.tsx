import { groupByLayout } from '@/app/placeholder-route';
import { clientsRouteSpecs } from '@/features/clients/route-specs';

/** Lazy placeholder routes; each feature port swaps a page in without touching the router. */
export const routes = groupByLayout(clientsRouteSpecs);
