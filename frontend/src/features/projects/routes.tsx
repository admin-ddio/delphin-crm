import { groupByLayout } from '@/app/placeholder-route';
import { projectsRouteSpecs } from '@/features/projects/route-specs';

export const routes = groupByLayout(projectsRouteSpecs, {
  '/projects': () => import('@/features/projects/ProjectsListPage'),
  '/projects/new': () => import('@/features/projects/NewProjectPage'),
  '/projects/:id': () => import('@/features/projects/ProjectPage'),
});
