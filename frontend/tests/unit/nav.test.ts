import { describe, expect, it } from 'vitest';
import { matchPath } from 'react-router';

import { ALL_ROUTE_SPECS } from '@/app/routes';
import { navGroups, quickActions, visibleNav, visibleQuickActions } from '@/components/shell/nav';
import { DEFAULT_ROLE_PERMISSIONS } from '@/lib/permissions';

const resolves = (href: string) =>
  ALL_ROUTE_SPECS.some((spec) => matchPath({ path: spec.path, end: true }, href));

const labelsFor = (role: keyof typeof DEFAULT_ROLE_PERMISSIONS) =>
  visibleNav(DEFAULT_ROLE_PERMISSIONS[role]).flatMap((group) =>
    group.items.map((item) => item.label),
  );

describe('navigation model', () => {
  it('links only to registered routes', () => {
    for (const item of navGroups.flatMap((group) => group.items)) {
      expect(resolves(item.href), item.href).toBe(true);
    }
    for (const action of quickActions) {
      expect(resolves(action.href), action.href).toBe(true);
    }
  });

  it('has unique hrefs', () => {
    const hrefs = navGroups.flatMap((group) => group.items.map((item) => item.href));
    expect(new Set(hrefs).size).toBe(hrefs.length);
  });

  it('matches the clickable demo rail plus the People group from the HR brief', () => {
    expect(navGroups.map((g) => [g.label, g.items.map((i) => i.label)])).toEqual([
      ['Overview', ['Dashboard']],
      ['Clients', ['CRM & Clients', 'Client Onboarding']],
      ['Delivery', ['Projects', 'Tasks & Work', 'Approvals']],
      ['Services', ['Services & Retainers']],
      ['People', ['Employees', 'Organization & Roles']],
      ['Organisation', ['Finance & Billing', 'Team & Roles', 'Activity log']],
    ]);
  });

  it('shows Finance only to roles that can see money (demo rule)', () => {
    expect(labelsFor('super_admin')).toContain('Finance & Billing');
    expect(labelsFor('account_manager')).toContain('Finance & Billing');
    expect(labelsFor('finance')).toContain('Finance & Billing');
    for (const role of ['project_manager', 'team_lead', 'employee'] as const) {
      expect(labelsFor(role), role).not.toContain('Finance & Billing');
    }
  });

  it('filters by permission and drops empty groups', () => {
    const groups = [
      {
        label: 'Money',
        items: [{ label: 'Finance', href: '/finance', permission: 'finance.view' }],
      },
      { label: 'Open', items: [{ label: 'Dashboard', href: '/dashboard' }] },
    ];
    expect(visibleNav([], groups).map((g) => g.label)).toEqual(['Open']);
    expect(visibleNav(['finance.view'], groups).map((g) => g.label)).toEqual(['Money', 'Open']);
    expect(visibleNav(['*'], groups)).toHaveLength(2);
  });

  it('filters quick actions', () => {
    expect(visibleQuickActions(DEFAULT_ROLE_PERMISSIONS.employee)).toEqual([]);
    expect(visibleQuickActions(DEFAULT_ROLE_PERMISSIONS.account_manager)).toHaveLength(1);
  });
});
