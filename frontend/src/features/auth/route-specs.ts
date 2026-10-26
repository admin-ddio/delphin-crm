import type { RouteSpec } from '@/app/route-spec';

/**
 * Pilot routes owned by the auth module. Titles are provisional (see RouteSpec.title).
 *
 * The pilot's /reset-password/:token and /activate/:token are replaced by Firebase
 * e-mail links handled at /auth/action (ADR-0009): password setup for invited
 * users and password resets both arrive as Firebase `resetPassword` links.
 */
export const authRouteSpecs: readonly RouteSpec[] = [
  {
    path: '/login',
    title: 'Sign in',
    module: 'auth',
    layout: 'public',
    screenshots: ['00-login.png'],
    ported: true,
  },
  // Not a pilot route: self sign-up added on request (pending admin approval).
  { path: '/signup', title: 'Create account', module: 'auth', layout: 'public', ported: true },
  {
    path: '/forgot-password',
    title: 'Forgot password',
    module: 'auth',
    layout: 'public',
    ported: true,
  },
  { path: '/auth/action', title: 'Account link', module: 'auth', layout: 'public', ported: true },
  { path: '/account', title: 'My account', module: 'auth', layout: 'app', ported: true },
];
