import { groupByLayout } from '@/app/placeholder-route';
import { servicesRouteSpecs } from '@/features/services/route-specs';

/** /services: list, workspace and templates; other pilot routes stay placeholders. */
export const routes = groupByLayout(servicesRouteSpecs, {
  '/services': () => import('@/features/services/ServicesPage'),
  '/services/:id': () => import('@/features/services/ServicePage'),
  '/services/templates': () => import('@/features/services/TemplatesPage'),
});
