import { groupByLayout } from '@/app/placeholder-route';
import { documentsRouteSpecs } from '@/features/documents/route-specs';

/** Lazy placeholder routes; each feature port swaps a page in without touching the router. */
export const routes = groupByLayout(documentsRouteSpecs);
