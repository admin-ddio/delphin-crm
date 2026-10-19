import { groupByLayout } from '@/app/placeholder-route';
import { clientsRouteSpecs } from '@/features/clients/route-specs';

const clientPage = () => import('@/features/clients/ClientPage');

/** Every client route renders its real page; one ClientPage serves the client and all its tabs. */
export const routes = groupByLayout(clientsRouteSpecs, {
  '/clients': () => import('@/features/clients/ClientsListPage'),
  '/clients/new': () => import('@/features/clients/NewClientPage'),
  ...Object.fromEntries(
    clientsRouteSpecs
      .filter((spec) => spec.path.startsWith('/clients/:id'))
      .map((spec) => [spec.path, clientPage]),
  ),
});
