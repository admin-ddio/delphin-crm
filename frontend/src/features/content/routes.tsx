import { groupByLayout } from '@/app/placeholder-route';
import { contentRouteSpecs } from '@/features/content/route-specs';

/** Lazy placeholder routes; each feature port swaps a page in without touching the router. */
export const routes = groupByLayout(contentRouteSpecs);
