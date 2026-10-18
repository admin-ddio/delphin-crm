import { groupByLayout } from '@/app/placeholder-route';
import { authRouteSpecs } from '@/features/auth/route-specs';

/** Every auth route renders its real page; titles still come from route-specs.ts. */
export const routes = groupByLayout(authRouteSpecs, {
  '/login': () => import('@/features/auth/LoginPage'),
  '/signup': () => import('@/features/auth/SignupPage'),
  '/forgot-password': () => import('@/features/auth/ForgotPasswordPage'),
  '/auth/action': () => import('@/features/auth/AuthActionPage'),
  '/account': () => import('@/features/auth/AccountPage'),
});
