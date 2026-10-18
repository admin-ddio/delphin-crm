import { groupByLayout } from '@/app/placeholder-route';
import { settingsRouteSpecs } from '@/features/settings/route-specs';

/** Lazy placeholder routes; each feature port swaps a page in without touching the router. */
export const routes = groupByLayout(settingsRouteSpecs);
