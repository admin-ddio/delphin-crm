import { createBrowserRouter, Navigate, type RouteObject } from 'react-router';

import type { RoutesByLayout } from '@/app/placeholder-route';
import { NotFoundPage, RouteErrorBoundary } from '@/components/ErrorBoundary';
import { AppLayout } from '@/components/shell/AppLayout';
import { BareLayout, PublicLayout } from '@/components/shell/PublicLayout';
import { routes as activity } from '@/features/activity/routes';
import { routes as approvals } from '@/features/approvals/routes';
import { routes as auth } from '@/features/auth/routes';
import { routes as clients } from '@/features/clients/routes';
import { routes as content } from '@/features/content/routes';
import { routes as dashboard } from '@/features/dashboard/routes';
import { routes as documents } from '@/features/documents/routes';
import { routes as finance } from '@/features/finance/routes';
import { routes as meetings } from '@/features/meetings/routes';
import { routes as notifications } from '@/features/notifications/routes';
import { routes as onboarding } from '@/features/onboarding/routes';
import { routes as projects } from '@/features/projects/routes';
import { routes as reports } from '@/features/reports/routes';
import { routes as search } from '@/features/search/routes';
import { routes as seo } from '@/features/seo/routes';
import { routes as services } from '@/features/services/routes';
import { routes as settings } from '@/features/settings/routes';
import { routes as tasks } from '@/features/tasks/routes';
import { routes as team } from '@/features/team/routes';

const FEATURES: RoutesByLayout[] = [
  auth,
  dashboard,
  notifications,
  clients,
  onboarding,
  projects,
  tasks,
  approvals,
  meetings,
  services,
  seo,
  content,
  team,
  documents,
  reports,
  finance,
  search,
  settings,
  activity,
];

const collect = (layout: keyof RoutesByLayout) => FEATURES.flatMap((feature) => feature[layout]);

const devRoutes: RouteObject[] = import.meta.env.DEV
  ? [
      {
        path: '/__dev/ui',
        handle: { title: 'UI primitives', module: 'settings' },
        lazy: () => import('@/features/__dev/UiGallery'),
      },
    ]
  : [];

export const routes: RouteObject[] = [
  {
    errorElement: <RouteErrorBoundary />,
    // Lazy routes resolve before first paint; render nothing meanwhile.
    HydrateFallback: () => null,
    children: [
      { element: <PublicLayout />, children: collect('public') },
      { element: <BareLayout />, children: collect('bare') },
      {
        element: <AppLayout />,
        children: [
          { index: true, element: <Navigate to="/dashboard" replace /> },
          ...collect('app'),
          ...devRoutes,
        ],
      },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
];

export function createAppRouter() {
  return createBrowserRouter(routes);
}
