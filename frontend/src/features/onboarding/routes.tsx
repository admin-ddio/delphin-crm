import { groupByLayout } from '@/app/placeholder-route';
import { onboardingRouteSpecs } from '@/features/onboarding/route-specs';

export const routes = groupByLayout(onboardingRouteSpecs, {
  '/onboarding': () => import('@/features/onboarding/OnboardingBoardPage'),
  '/q/:token': () => import('@/features/onboarding/PublicQuestionnairePage'),
});
