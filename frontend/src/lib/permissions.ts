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

export function canAny(
  granted: readonly Permission[],
  permissions: readonly Permission[],
): boolean {
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
  projectsViewAll: 'projects.view_all',
  tasksCreate: 'tasks.create',
  tasksReview: 'tasks.review',
  clientDecisionRecord: 'approvals.client_decision',
  retainersManage: 'services.manage',
  servicesManage: 'services.manage',
  servicesViewAll: 'services.view_all',
  servicesTemplatesManage: 'services.templates.manage',
  jobsRun: 'jobs.run',
  financeManage: 'finance.manage',
  financeView: 'finance.view',
  usersApprove: 'users.approve',
  usersManage: 'users.manage',
  meetingsManage: 'meetings.manage',
  hrManage: 'hr.manage',
  hrViewAll: 'hr.view_all',
  hrPersonalView: 'hr.personal.view',
  // Organization & Role Settings (Organization brief §8).
  orgView: 'org.view',
  orgDirectoryView: 'org.directory.view',
  orgTeamView: 'org.team.view',
  orgDepartmentsManage: 'org.departments.manage',
  orgDesignationsManage: 'org.designations.manage',
  orgReportingManage: 'org.reporting.manage',
  orgProjectsAssign: 'org.projects.assign',
  orgRolesManage: 'org.roles.manage',
  orgRolesAssign: 'org.roles.assign',
  orgAuditView: 'org.audit.view',
} as const;

/** Any of these opens Organization & Role Settings beyond the read-only chart. */
export const ORG_SETTINGS: readonly Permission[] = [
  P.orgDepartmentsManage,
  P.orgDesignationsManage,
  P.orgReportingManage,
  P.orgProjectsAssign,
  P.orgRolesManage,
  P.orgRolesAssign,
  P.orgAuditView,
];

/** Everyone signed in may look at the organisation and the directory. */
const EVERYONE: readonly Permission[] = [P.orgView, P.orgDirectoryView];

export const ROLE_KEYS = [
  'super_admin',
  'admin',
  'account_manager',
  'project_manager',
  'team_lead',
  'employee',
  'finance',
  'hr_admin',
  'org_admin',
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
  hr_admin: 'HR / Operations Admin',
  org_admin: 'Organization Admin',
};

/**
 * From the demo. `admin` is in the scaffold brief but NOT in the demo, so it has
 * no permissions until permissions.ts is ported.
 */
export const DEFAULT_ROLE_PERMISSIONS: Record<RoleKey, readonly Permission[]> = {
  super_admin: [WILDCARD],
  admin: [...EVERYONE],
  account_manager: [
    ...EVERYONE,
    P.orgTeamView,
    P.clientsCreate,
    P.clientsViewAll,
    P.clientsUpdate,
    P.onboardingManage,
    P.accessVerify,
    P.kpiConfirm,
    P.projectsCreate,
    P.projectsViewAll,
    P.tasksCreate,
    P.clientDecisionRecord,
    P.retainersManage,
    P.servicesViewAll,
    P.financeView,
    P.meetingsManage,
  ],
  project_manager: [
    ...EVERYONE,
    P.orgTeamView,
    P.orgProjectsAssign,
    P.servicesViewAll,
    P.servicesTemplatesManage,
    P.clientsViewAll,
    P.projectsCreate,
    P.projectsViewAll,
    P.tasksCreate,
    P.tasksReview,
    P.accessVerify,
    P.jobsRun,
    P.meetingsManage,
  ],
  team_lead: [
    ...EVERYONE,
    P.orgTeamView,
    P.tasksCreate,
    P.tasksReview,
    P.accessVerify,
    P.meetingsManage,
  ],
  employee: [...EVERYONE],
  finance: [
    ...EVERYONE,
    P.servicesViewAll,
    P.clientsViewAll,
    P.projectsViewAll,
    P.financeManage,
    P.financeView,
  ],
  // Employee records only; organisation structure belongs to org_admin.
  hr_admin: [...EVERYONE, P.orgTeamView, P.hrManage, P.hrViewAll, P.hrPersonalView],
  // Organization brief §7: this module only, nothing else.
  org_admin: [
    ...EVERYONE,
    P.orgTeamView,
    P.orgDepartmentsManage,
    P.orgDesignationsManage,
    P.orgReportingManage,
    P.orgProjectsAssign,
    P.orgRolesManage,
    P.orgRolesAssign,
    P.orgAuditView,
  ],
};
