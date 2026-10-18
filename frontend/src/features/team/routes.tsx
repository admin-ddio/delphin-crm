import { groupByLayout } from '@/app/placeholder-route';
import { teamRouteSpecs } from '@/features/team/route-specs';

/** /team shows sign-up approvals (ported); the other team routes are placeholders. */
export const routes = groupByLayout(teamRouteSpecs, {
  '/team': () => import('@/features/team/TeamPage'),
});
