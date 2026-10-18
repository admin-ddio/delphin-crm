import type { RouteSpec } from '@/app/route-spec';

/** Pilot routes owned by the onboarding module. Titles are provisional (see RouteSpec.title). */
export const onboardingRouteSpecs: readonly RouteSpec[] = [
  { path: '/onboarding', title: 'Client onboarding', module: 'onboarding', layout: 'app', titleSource: 'demo' },
  { path: '/q/:token', title: 'Client questionnaire', module: 'onboarding', layout: 'bare' },
];
