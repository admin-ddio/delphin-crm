import { groupByLayout } from '@/app/placeholder-route';
import { teamRouteSpecs } from '@/features/team/route-specs';

/** /team: sign-up approvals. /team/employees…, /team/teams: the people core. */
export const routes = groupByLayout(teamRouteSpecs, {
  '/team': () => import('@/features/team/TeamPage'),
  '/team/employees': () => import('@/features/team/EmployeesPage'),
  '/team/employees/new': () => import('@/features/team/NewEmployeePage'),
  '/team/employees/:id': () => import('@/features/team/EmployeePage'),
  '/team/teams': () => import('@/features/team/OrgSettingsPage'),
});
