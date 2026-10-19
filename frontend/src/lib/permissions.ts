/**
 * Client-side permission checks. They only shape the UI (nav, buttons); the API
 * re-checks every request. Mirrors backend/app/authz/permissions.py.
 *
 * INTERIM SOURCE: the clickable demo's role/capability matrix. Replace with
 * reference/pilot/nextjs-app/src/server/authz/permissions.ts when it arrives.
 */

export const WILDCARD = '*';

export type Permission = string;
export type PermissionRule = Permission | readonly Permission[] | undefined;

export function can(granted: readonly Permission[], permission: Permission): boolean {
  return granted.includes(WILDCARD) || granted.includes(permission);
}

export function canAny(granted: readonly Permission[], permissions: readonly Permission[]): boolean {
  return permissions.some((permission) => can(granted, permission));
}

/** undefined = visible to every signed-in user; a list = any of them. */
export function satisfies(granted: readonly Permission[], rule: PermissionRule): boolean {
  if (rule === undefined) return true;
  return typeof rule === 'string' ? can(granted, rule) : canAny(granted, rule);
}

/** Interim catalogue (demo capabilities, renamed to `domain.action`). */
export const P = {
  clientsCreate: 'clients.create',
  clientsViewAll: 'clients.view_all',
  clientsUpdate: 'clients.update',
  onboardingManage: 'onboarding.manage',
  accessVerify: 'onboarding.access_verify',
  kpiConfirm: 'onboarding.kpi_confirm',
  projectsCreate: 'projects.create',
  tasksCreate: 'tasks.create',
  tasksReview: 'tasks.review',
  clientDecisionRecord: 'approvals.client_decision',
  retainersManage: 'services.manage',
  jobsRun: 'jobs.run',
  financeManage: 'finance.manage',
  financeView: 'finance.view',
  usersApprove: 'users.approve',
} as const;

export const ROLE_KEYS = [
  'super_admin',
  'admin',
  'account_manager',
  'project_manager',
  'team_lead',
  'employee',
  'finance',
] as const;
export type RoleKey = (typeof ROLE_KEYS)[number];

export const ROLE_LABELS: Record<RoleKey, string> = {
  super_admin: 'Super Admin',
  admin: 'Admin / Operations Manager',
  account_manager: 'Account Manager',
  project_manager: 'Project Manager',
  team_lead: 'Team Lead',
  employee: 'Employee / Specialist',
  finance: 'Finance',
};

/**
 * From the demo. `admin` is in the scaffold brief but NOT in the demo, so it has
 * no permissions until permissions.ts is ported.
 */
export const DEFAULT_ROLE_PERMISSIONS: Record<RoleKey, readonly Permission[]> = {
  super_admin: [WILDCARD],
  admin: [],
  account_manager: [
    P.clientsCreate,
    P.clientsViewAll,
    P.clientsUpdate,
    P.onboardingManage,
    P.accessVerify,
    P.kpiConfirm,
    P.projectsCreate,
    P.tasksCreate,
    P.clientDecisionRecord,
    P.retainersManage,
    P.financeView,
  ],
  project_manager: [P.clientsViewAll, P.projectsCreate, P.tasksCreate, P.tasksReview, P.accessVerify, P.jobsRun],
  team_lead: [P.tasksCreate, P.tasksReview, P.accessVerify],
  employee: [],
  finance: [P.clientsViewAll, P.financeManage, P.financeView],
};
