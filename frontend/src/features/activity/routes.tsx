import { groupByLayout } from '@/app/placeholder-route';
import { activityRouteSpecs } from '@/features/activity/route-specs';

/** /activity: the activity log. */
export const routes = groupByLayout(activityRouteSpecs, {
  '/activity': () => import('@/features/activity/ActivityPage'),
});
