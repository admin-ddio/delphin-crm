import { groupByLayout } from '@/app/placeholder-route';
import { onboardingRouteSpecs } from '@/features/onboarding/route-specs';

/** Lazy placeholder routes; each feature port swaps a page in without touching the router. */
export const routes = groupByLayout(onboardingRouteSpecs);
