import { groupByLayout } from '@/app/placeholder-route';
import { projectsRouteSpecs } from '@/features/projects/route-specs';

/** Lazy placeholder routes; each feature port swaps a page in without touching the router. */
export const routes = groupByLayout(projectsRouteSpecs);
