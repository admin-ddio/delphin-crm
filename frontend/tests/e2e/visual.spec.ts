/**
 * Visual parity against reference/pilot/screenshots (1440 × 900, deviceScaleFactor 1,
 * light, full page), maxDiffPixelRatio ≤ 0.01.
 *
 * Tests skip (never fake a pass) while a baseline is missing, unless
 * REQUIRE_PILOT=true, in which case they fail.
 */
import { expect, test } from '@playwright/test';

import { pilotRequired } from '../pilot';
import { AUTH_FILE, SIGNED_OUT } from './auth';
import { diffAgainstBaseline, hasBaseline, MAX_DIFF_RATIO, stabilise } from './pixel-diff';

function requireBaseline(file: string): void {
  if (hasBaseline(file)) return;
  if (pilotRequired()) throw new Error(`Missing pilot baseline ${file}`);
  test.skip(true, `pilot baseline ${file} not present in reference/pilot/screenshots`);
}

test.describe('visual parity: sign-in (signed out)', () => {
  test.use({ storageState: SIGNED_OUT });

  test('sign-in page matches 00-login.png', async ({ page }, testInfo) => {
    requireBaseline('00-login.png');
    await page.goto('/login');
    await stabilise(page);
    expect(await diffAgainstBaseline(page, testInfo, '00-login.png')).toBeLessThanOrEqual(
      MAX_DIFF_RATIO,
    );
  });
});

test.describe('visual parity: scaffold scope', () => {
  test.use({ storageState: AUTH_FILE });

  test('shell sidebar matches the left region of 01-dashboard.png', async ({ page }, testInfo) => {
    requireBaseline('01-dashboard.png');
    await page.goto('/dashboard');
    await stabilise(page);
    const box = await page.getByTestId('app-sidebar').boundingBox();
    if (!box) throw new Error('sidebar not rendered');
    const clip = { x: 0, y: 0, width: Math.round(box.width), height: 900 };
    expect(await diffAgainstBaseline(page, testInfo, '01-dashboard.png', clip)).toBeLessThanOrEqual(
      MAX_DIFF_RATIO,
    );
  });

  test('shell top bar matches the top region of 01-dashboard.png', async ({ page }, testInfo) => {
    requireBaseline('01-dashboard.png');
    await page.goto('/dashboard');
    await stabilise(page);
    const box = await page.getByTestId('app-topbar').boundingBox();
    if (!box) throw new Error('top bar not rendered');
    const clip = {
      x: Math.round(box.x),
      y: 0,
      width: Math.round(box.width),
      height: Math.round(box.height),
    };
    expect(await diffAgainstBaseline(page, testInfo, '01-dashboard.png', clip)).toBeLessThanOrEqual(
      MAX_DIFF_RATIO,
    );
  });

  test('primitives gallery matches the pilot gallery baseline', async ({ page }, testInfo) => {
    // No pilot gallery baseline exists yet: it must be captured from a running pilot
    // (docs/testing.md). Recorded as a gap in docs/pilot-parity.md.
    requireBaseline('dev-ui-gallery.png');
    await page.goto('/__dev/ui');
    await stabilise(page);
    expect(await diffAgainstBaseline(page, testInfo, 'dev-ui-gallery.png')).toBeLessThanOrEqual(
      MAX_DIFF_RATIO,
    );
  });
});

/** Business screens: each feature port turns its entry on (test.fixme -> test). */
test.describe('visual parity: business screens (pending feature ports)', () => {
  const pending: [file: string, screen: string][] = [
    ['01-dashboard.png', 'Organisation dashboard (full page)'],
    ['02-clients.png', 'CRM & Clients list'],
    ['03-client-overview.png', 'Client overview'],
    ['04-onboarding-summary.png', 'Onboarding: summary'],
    ['05-onboarding-access.png', 'Onboarding: access'],
    ['06-onboarding-kpis.png', 'Onboarding: KPIs'],
    ['07-onboarding-review.png', 'Onboarding: review'],
    ['08-project.png', 'Project overview'],
    ['09-project-board.png', 'Project kanban board'],
    ['10-task.png', 'Task detail'],
    ['11-approval.png', 'Approval decision'],
    ['12-retainer-workspace.png', 'Service / retainer workspace'],
    ['13-content.png', 'Content & Social'],
    ['14-invoice.png', 'Invoice detail'],
    ['15-finance.png', 'Finance overview'],
    ['16-team.png', 'Team & Employees'],
    ['17-settings-roles.png', 'Settings → Roles & permissions'],
  ];
  for (const [file, screen] of pending) {
    test.fixme(`${screen} matches ${file}`, async () => {});
  }
});
