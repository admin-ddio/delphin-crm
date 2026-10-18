/** The full pilot route inventory, aggregated from every feature (pure data). */
import type { RouteSpec } from '@/app/route-spec';
import { activityRouteSpecs } from '@/features/activity/route-specs';
import { approvalsRouteSpecs } from '@/features/approvals/route-specs';
import { authRouteSpecs } from '@/features/auth/route-specs';
import { clientsRouteSpecs } from '@/features/clients/route-specs';
import { contentRouteSpecs } from '@/features/content/route-specs';
import { dashboardRouteSpecs } from '@/features/dashboard/route-specs';
import { documentsRouteSpecs } from '@/features/documents/route-specs';
import { financeRouteSpecs } from '@/features/finance/route-specs';
import { meetingsRouteSpecs } from '@/features/meetings/route-specs';
import { notificationsRouteSpecs } from '@/features/notifications/route-specs';
import { onboardingRouteSpecs } from '@/features/onboarding/route-specs';
import { projectsRouteSpecs } from '@/features/projects/route-specs';
import { reportsRouteSpecs } from '@/features/reports/route-specs';
import { searchRouteSpecs } from '@/features/search/route-specs';
import { seoRouteSpecs } from '@/features/seo/route-specs';
import { servicesRouteSpecs } from '@/features/services/route-specs';
import { settingsRouteSpecs } from '@/features/settings/route-specs';
import { tasksRouteSpecs } from '@/features/tasks/route-specs';
import { teamRouteSpecs } from '@/features/team/route-specs';

export const ALL_ROUTE_SPECS: readonly RouteSpec[] = [
  ...authRouteSpecs,
  ...dashboardRouteSpecs,
  ...notificationsRouteSpecs,
  ...clientsRouteSpecs,
  ...onboardingRouteSpecs,
  ...projectsRouteSpecs,
  ...tasksRouteSpecs,
  ...approvalsRouteSpecs,
  ...meetingsRouteSpecs,
  ...servicesRouteSpecs,
  ...seoRouteSpecs,
  ...contentRouteSpecs,
  ...teamRouteSpecs,
  ...documentsRouteSpecs,
  ...reportsRouteSpecs,
  ...financeRouteSpecs,
  ...searchRouteSpecs,
  ...settingsRouteSpecs,
  ...activityRouteSpecs,
];
