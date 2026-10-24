/**
 * Navigation model.
 *
 * INTERIM SOURCE: the clickable demo's rail (groups, labels, order, badges, the
 * Finance visibility rule; no icons). Must be replaced 1:1 by
 * reference/pilot/nextjs-app/src/components/shell/nav.ts.
 *
 * Pilot routes that the demo's rail does not show (notifications, meetings, SEO,
 * content, documents, reports, search, settings) stay registered and reachable by
 * URL; the pilot's nav.ts decides where they appear.
 */
import { P, satisfies, type PermissionRule } from '@/lib/permissions';

/** Live counters shown as a badge next to an item. */
export type NavBadge = 'myOpenTasks' | 'myPendingApprovals';
export type NavBadgeCounts = Partial<Record<NavBadge, number>>;

export interface NavItem {
  label: string;
  href: string;
  /** Visible when the actor satisfies this rule (undefined = everyone signed in). */
  permission?: PermissionRule;
  badge?: NavBadge;
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

export const navGroups: NavGroup[] = [
  { label: 'Overview', items: [{ label: 'Dashboard', href: '/dashboard' }] },
  {
    label: 'Clients',
    items: [
      { label: 'CRM & Clients', href: '/clients' },
      { label: 'Client Onboarding', href: '/onboarding' },
    ],
  },
  {
    label: 'Delivery',
    items: [
      { label: 'Projects', href: '/projects' },
      { label: 'Tasks & Work', href: '/tasks', badge: 'myOpenTasks' },
      { label: 'Approvals', href: '/approvals', badge: 'myPendingApprovals' },
    ],
  },
  { label: 'Services', items: [{ label: 'Services & Retainers', href: '/services' }] },
  {
    // From the HR brief (not in the demo rail).
    label: 'People',
    items: [
      { label: 'Employees', href: '/team/employees' },
      { label: 'Organization & Roles', href: '/team/teams' },
    ],
  },
  {
    label: 'Organisation',
    items: [
      {
        label: 'Finance & Billing',
        href: '/finance',
        permission: [P.financeManage, P.financeView],
      },
      { label: 'Team & Roles', href: '/team' },
      { label: 'Activity log', href: '/activity' },
    ],
  },
];

export interface QuickAction {
  label: string;
  href: string;
  permission?: PermissionRule;
}

/** The scaffold brief says the pilot's nav.ts has quickActions; the demo shows none. */
export const quickActions: QuickAction[] = [
  { label: 'New client', href: '/clients/new', permission: P.clientsCreate },
];

/** Groups and items the actor may see; empty groups are dropped. */
export function visibleNav(
  permissions: readonly string[],
  groups: NavGroup[] = navGroups,
): NavGroup[] {
  return groups
    .map((group) => ({
      ...group,
      items: group.items.filter((item) => satisfies(permissions, item.permission)),
    }))
    .filter((group) => group.items.length > 0);
}

export function visibleQuickActions(
  permissions: readonly string[],
  actions: QuickAction[] = quickActions,
): QuickAction[] {
  return actions.filter((action) => satisfies(permissions, action.permission));
}
