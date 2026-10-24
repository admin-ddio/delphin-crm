import { expect, test, type Locator, type Page } from '@playwright/test';

import { samplePath } from '../../src/app/route-spec';
import { ALL_ROUTE_SPECS } from '../../src/app/routes';
import {
  AUTH_FILE,
  E2E_EMAIL,
  E2E_PASSWORD,
  FLOWS_EMAIL,
  latestOobCode,
  resetEmulatorAccount,
  SIGNED_OUT,
} from './auth';

const FLOWS_PASSWORD = 'flows-password-original';
const FLOWS_NEW_PASSWORD = 'flows-password-changed-1';

/** Every registered pilot route renders its page with its title. */
test.describe('signed-in pages', () => {
  test.use({ storageState: AUTH_FILE });

  for (const spec of ALL_ROUTE_SPECS.filter((s) => s.layout === 'app')) {
    test(`${spec.path} renders "${spec.title}"`, async ({ page }) => {
      await page.goto(samplePath(spec.path));
      // Ported pages title themselves from data (e.g. the client's name); placeholders use the spec.
      const heading = spec.ported
        ? page.getByRole('heading', { level: 1 })
        : page.getByRole('heading', { level: 1, name: spec.title, exact: true });
      await expect(heading).toBeVisible();
      await expect(page.getByTestId('app-sidebar')).toBeAttached();
      await expect(page.getByTestId('app-topbar')).toBeVisible();
    });
  }

  test('dashboard greets the user and counts clients', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page.getByRole('heading', { level: 1, name: 'Good day, E2E' })).toBeVisible();
    const tiles = page.getByTestId('dashboard-tiles');
    await expect(tiles.getByText('Active clients')).toBeVisible();
    await expect(tiles.getByText(/^\d+$/).first()).toBeVisible();
    await expect(page.getByRole('link', { name: 'Create a client' })).toBeVisible();
    await expect(page.getByRole('link', { name: /Review sign-ups/ })).toBeVisible();
  });

  test('the app reaches the API and receives a CSRF cookie', async ({ page, context }) => {
    await page.goto('/dashboard');
    // The dashboard fires several requests at once; under parallel load this can take a while.
    await expect(page.getByTestId('api-status')).toHaveText('API connected', { timeout: 15_000 });
    const cookies = await context.cookies();
    expect(cookies.map((cookie) => cookie.name)).toContain('delphin_csrf');
  });

  test('primitives gallery renders (dev only)', async ({ page }) => {
    await page.goto('/__dev/ui');
    await expect(page.getByTestId('ui-gallery')).toBeVisible();
  });

  /**
   * TODO(pilot-port): once nav.ts and permissions.ts are ported, sign in as one
   * user per default role and assert the visible nav labels equal the pilot's.
   */
  test.fixme('nav matches the pilot for each default role', async () => {});
});

test.describe('signed-out pages', () => {
  test.use({ storageState: SIGNED_OUT });

  for (const spec of ALL_ROUTE_SPECS.filter((s) => s.layout !== 'app')) {
    test(`${spec.path} renders "${spec.title}"`, async ({ page }) => {
      await page.goto(samplePath(spec.path));
      await expect(
        page.getByRole('heading', { level: 1, name: spec.title, exact: true }),
      ).toBeVisible();
    });
  }

  test('app pages send signed-out visitors to sign in', async ({ page }) => {
    await page.goto('/clients');
    await expect(page).toHaveURL(/\/login$/);
  });

  test('API is reachable through the dev proxy', async ({ request }) => {
    const response = await request.get('/api/v1/openapi.json');
    expect(response.ok()).toBeTruthy();
    const document = (await response.json()) as { tags: { name: string }[] };
    expect(document.tags.map((tag) => tag.name)).toContain('clients');
  });
});

test.describe('sign-in journey', () => {
  test.use({ storageState: SIGNED_OUT });

  test('wrong password shows a generic error', async ({ page }) => {
    await page.goto('/login');
    await page.getByLabel('Email').fill(E2E_EMAIL);
    await page.getByLabel('Password').fill('definitely-wrong');
    await page.getByRole('button', { name: 'Sign in' }).click();
    await expect(page.getByRole('alert')).toHaveText('Invalid email or password.');
  });

  test('sign in, land where you were going, then sign out', async ({ page }) => {
    await page.goto('/projects');
    await expect(page).toHaveURL(/\/login$/);
    await page.getByLabel('Email').fill(E2E_EMAIL);
    await page.getByLabel('Password').fill(E2E_PASSWORD);
    await page.getByRole('button', { name: 'Sign in' }).click();

    await expect(page).toHaveURL(/\/projects$/);
    await expect(page.getByTestId('current-user')).toContainText('E2E Admin');

    await page.reload(); // the session survives a reload (cookie + /auth/me)
    await expect(page.getByRole('heading', { level: 1, name: 'Projects' })).toBeVisible();

    await page.getByTestId('current-user').click();
    await page.getByRole('menuitem', { name: 'Sign out' }).click();
    await expect(page).toHaveURL(/\/login$/);
    await page.goto('/dashboard');
    await expect(page).toHaveURL(/\/login$/);
  });
});

test.describe('e-mail journeys (Firebase emulator)', () => {
  test.use({ storageState: SIGNED_OUT });
  // Both journeys mutate the same Firebase account.
  test.describe.configure({ mode: 'serial' });

  test.beforeEach(async ({ request }) => {
    await resetEmulatorAccount(request, FLOWS_EMAIL, {
      password: FLOWS_PASSWORD,
      emailVerified: false,
    });
  });

  test('unverified e-mail: resend, open the link, then sign in', async ({ page, request }) => {
    await page.goto('/login');
    await page.getByLabel('Email').fill(FLOWS_EMAIL);
    await page.getByLabel('Password').fill(FLOWS_PASSWORD);
    await page.getByRole('button', { name: 'Sign in' }).click();
    await expect(page.getByText('Verify your e-mail address')).toBeVisible();

    await page.getByRole('button', { name: 'Resend verification e-mail' }).click();
    await expect(page.getByText('Check your inbox.')).toBeVisible();

    const code = await latestOobCode(request, FLOWS_EMAIL, 'VERIFY_EMAIL');
    await page.goto(`/auth/action?mode=verifyEmail&oobCode=${code}`);
    await expect(page.getByText('Your e-mail address is verified.')).toBeVisible();

    await page.getByRole('link', { name: 'Sign in' }).click();
    await page.getByLabel('Email').fill(FLOWS_EMAIL);
    await page.getByLabel('Password').fill(FLOWS_PASSWORD);
    await page.getByRole('button', { name: 'Sign in' }).click();
    await expect(page).toHaveURL(/\/dashboard$/);
  });

  test('forgot password: e-mail link, new password, sign in', async ({ page, request }) => {
    await resetEmulatorAccount(request, FLOWS_EMAIL, { emailVerified: true });
    await page.goto('/forgot-password');
    await page.getByLabel('Email').fill(FLOWS_EMAIL);
    await page.getByRole('button', { name: 'Send reset link' }).click();
    await expect(page.getByText("we've sent a link to reset the password")).toBeVisible();

    const code = await latestOobCode(request, FLOWS_EMAIL, 'PASSWORD_RESET');
    await page.goto(`/auth/action?mode=resetPassword&oobCode=${code}`);
    await expect(page.getByText(FLOWS_EMAIL)).toBeVisible();
    await page.getByLabel('New password', { exact: true }).fill(FLOWS_NEW_PASSWORD);
    await page.getByLabel('Confirm new password').fill(FLOWS_NEW_PASSWORD);
    await page.getByRole('button', { name: 'Change password' }).click();
    await expect(page.getByText('Your password has been changed.')).toBeVisible();

    await page.goto('/login');
    await page.getByLabel('Email').fill(FLOWS_EMAIL);
    await page.getByLabel('Password').fill(FLOWS_PASSWORD);
    await page.getByRole('button', { name: 'Sign in' }).click();
    await expect(page.getByRole('alert')).toHaveText('Invalid email or password.');
    await page.getByLabel('Password').fill(FLOWS_NEW_PASSWORD);
    await page.getByRole('button', { name: 'Sign in' }).click();
    await expect(page).toHaveURL(/\/dashboard$/);
  });

  test('a used or bogus link is rejected', async ({ page }) => {
    await page.goto('/auth/action?mode=verifyEmail&oobCode=not-a-real-code');
    await expect(page.getByText('This link is invalid or has expired.')).toBeVisible();
  });
});

test.describe('self sign-up with admin approval', () => {
  test.use({ storageState: SIGNED_OUT });
  // Sign-up = 4 round trips (Firebase create, profile, verification e-mail, app register).
  const SLOW = 20_000;

  test('sign up → verify e-mail → wait → admin approves → sign in', async ({
    page,
    request,
    browser,
  }) => {
    const email = `signup-${Date.now()}@example.com`;
    const password = 'signup-password-123';

    // 1. Sign up from the login page.
    await page.goto('/login');
    await page.getByRole('link', { name: 'Sign up' }).click();
    await expect(page.getByRole('heading', { level: 1, name: 'Create account' })).toBeVisible();
    await page.getByLabel('Full name').fill('Sam Signup');
    await page.getByLabel('Email').fill(email);
    await page.getByLabel('Password', { exact: true }).fill(password);
    await page.getByLabel('Confirm password').fill(password);
    await page.getByRole('button', { name: 'Create account' }).click();
    await expect(page.getByText('Check your inbox')).toBeVisible({ timeout: SLOW });

    // 2. Not verified yet: sign-in is refused.
    const signIn = async () => {
      await page.goto('/login');
      await page.getByLabel('Email').fill(email);
      await page.getByLabel('Password').fill(password);
      await page.getByRole('button', { name: 'Sign in' }).click();
    };
    await signIn();
    await expect(page.getByText('Verify your e-mail address')).toBeVisible({ timeout: SLOW });

    // 3. Open the verification link from the (emulated) inbox.
    const code = await latestOobCode(request, email, 'VERIFY_EMAIL');
    await page.goto(`/auth/action?mode=verifyEmail&oobCode=${code}`);
    await expect(page.getByText('Your e-mail address is verified.')).toBeVisible();

    // 4. Verified but not approved: still no access.
    await signIn();
    await expect(page.getByText('Waiting for approval')).toBeVisible({ timeout: SLOW });

    // 5. A Super Admin approves the sign-up on Team & roles.
    const adminContext = await browser.newContext({ storageState: AUTH_FILE });
    const admin = await adminContext.newPage();
    await admin.goto('/team');
    const row = admin.getByTestId('pending-registration').filter({ hasText: email });
    await expect(row).toBeVisible();
    await expect(row.getByText('Verified')).toBeVisible();
    await row.getByLabel('Role for Sam Signup').selectOption('account_manager');
    await row.getByRole('button', { name: 'Approve' }).click();
    await expect(admin.getByText('Sam Signup approved as Account Manager.')).toBeVisible({
      timeout: SLOW,
    });
    await expect(row).toHaveCount(0);
    await adminContext.close();

    // 6. Now they get in, with the chosen role.
    await signIn();
    await expect(page).toHaveURL(/\/dashboard$/, { timeout: SLOW });
    await expect(page.getByTestId('current-user')).toContainText('Sam Signup');
    await expect(page.getByTestId('current-user')).toContainText('Account Manager');
  });
});

/** Fill Screen 2 (Create New Client) with a complete profile and contract. */
async function fillClientForm(
  page: Page,
  {
    name,
    website,
    industry = 'Manufacturing',
  }: { name: string; website: string; industry?: string },
) {
  await page.getByLabel('Company Name *').fill(name);
  await page.getByLabel('Website').fill(website);
  await page.getByLabel('Industry *').selectOption({ label: industry });
  await page.getByLabel('Business Type').selectOption({ label: 'B2B' });
  await page.getByLabel('Contact Name *').fill('Pat Buyer');
  await page.getByLabel('Designation *').fill('Marketing Head');
  await page.getByLabel('Email *', { exact: true }).fill('pat@example.com');
  await page.getByLabel('Phone *').fill('98765 43210');
  await page.getByLabel('Account Manager *').selectOption({ label: 'E2E Admin' });
  await page.getByLabel('Contract Start Date *').fill('2026-05-01');
  await page.getByLabel('Contract End Date *').fill('2027-04-30');
  await page.getByLabel('Contract Value (INR)').fill('500000');
}

test.describe('clients', () => {
  test.use({ storageState: AUTH_FILE });

  test('create with contract, duplicate rules, list, edit, documents and status', async ({
    page,
  }) => {
    test.setTimeout(120_000);
    const stamp = Date.now();
    const name = `Playwright Widgets ${stamp}`;
    const domain = `pw-widgets-${stamp}.example`;

    // Create (Screen 2), with the signed contract attached.
    await page.goto('/clients');
    await page.getByRole('link', { name: 'New Client' }).click();
    await expect(page.getByRole('heading', { level: 1, name: 'Create New Client' })).toBeVisible();
    await shot(page, '02-create-client');
    await fillClientForm(page, { name, website: `https://www.${domain}/home` });
    await page.getByLabel('Contract file').setInputFiles({
      name: 'signed-contract.pdf',
      mimeType: 'application/pdf',
      buffer: Buffer.from('%PDF-1.7 e2e'),
    });
    await page.getByRole('button', { name: 'Save & Continue' }).click();
    await expect(page.getByRole('heading', { level: 1 })).toContainText(name);
    await expect(page.getByRole('heading', { level: 1 }).getByText('Onboarding')).toBeVisible();
    const clientUrl = page.url();

    // Same domain: hard block, even when "different business" is ticked.
    await page.goto('/clients/new');
    await fillClientForm(page, { name: `Unrelated ${stamp}`, website: domain });
    await page.getByLabel(/This is a different business/).check();
    await page.getByRole('button', { name: 'Save & Continue' }).click();
    await expect(page.getByRole('alert')).toContainText(`domain ${domain} already exists`);

    // Similar name: warning until confirmed.
    await page.getByLabel('Company Name *').fill(`${name} Ltd.`);
    await page.getByLabel('Website').fill('');
    await page.getByLabel(/This is a different business/).uncheck();
    await page.getByRole('button', { name: 'Save & Continue' }).click();
    await expect(page.getByText('Possible duplicate')).toBeVisible();
    await page.getByLabel(/This is a different business/).check();
    await page.getByRole('button', { name: 'Save & Continue' }).click();
    await expect(page.getByRole('heading', { level: 1 })).toContainText(`${name} Ltd.`);

    // Screen 1: search, status tab, progress, last activity.
    await page.goto('/clients');
    await page.getByLabel('Search clients').fill(domain);
    const table = page.getByTestId('clients-table');
    await expect(table.getByRole('link', { name, exact: true })).toBeVisible();
    await expect(table.getByRole('row')).toHaveCount(2); // header + 1 match
    await expect(table.getByText('just now').or(table.getByText(/min/)).first()).toBeVisible();
    await shot(page, '01-client-list');
    await page.getByRole('tab', { name: /^Onboarding/ }).click();
    await expect(table.getByRole('link', { name, exact: true })).toBeVisible();

    // Edit, then see it in the activity log; the contract is in Documents.
    await page.goto(clientUrl);
    await page.getByRole('button', { name: 'Actions', exact: true }).click();
    await page.getByRole('menuitem', { name: 'Edit client' }).click();
    await page.getByLabel('Industry *').selectOption({ label: 'Healthcare' });
    await page.getByRole('button', { name: 'Save changes' }).click();
    await expect(page.getByText('Client updated.')).toBeVisible();
    await page.getByRole('link', { name: 'Activity', exact: true }).click();
    await expect(page.getByText('Client details updated: industry')).toBeVisible();
    await expect(page.getByText(`Client ${name} created`)).toBeVisible();
    await page.getByRole('link', { name: 'Documents', exact: true }).click();
    await expect(
      page.getByTestId('documents-table').getByText('signed-contract.pdf'),
    ).toBeVisible();

    // Lifecycle: On hold, then reactivate.
    await page.getByRole('button', { name: 'Actions', exact: true }).click();
    await page.getByRole('menuitem', { name: 'Put on hold' }).click();
    await expect(page.getByRole('heading', { level: 1 }).getByText('On hold')).toBeVisible();
    await page.getByRole('button', { name: 'Actions', exact: true }).click();
    await page.getByRole('menuitem', { name: 'Reactivate' }).click();
    await expect(page.getByRole('heading', { level: 1 }).getByText('Onboarding')).toBeVisible();
  });
});

test.describe('onboarding', () => {
  test.use({ storageState: AUTH_FILE });

  test('all 13 steps, the public questionnaire, the first project and its reviews', async ({
    page,
    browser,
  }) => {
    test.setTimeout(300_000);
    const stamp = Date.now();
    const name = `Onboarding Ltd ${stamp}`;

    // 1–3. Contract and profile captured at creation.
    await page.goto('/clients/new');
    await fillClientForm(page, { name, website: `onboarding-${stamp}.example` });
    await page.getByRole('button', { name: 'Save & Continue' }).click();
    await expect(page.getByRole('heading', { level: 1 })).toContainText(name);
    const clientPath = new URL(page.url()).pathname;
    const onboarding = page.getByTestId('onboarding');
    await expect(onboarding.getByText('23%')).toBeVisible();
    await expect(
      page.getByTestId('next-steps').getByText('Send the onboarding questionnaire'),
    ).toBeVisible();

    // 4–5. Questionnaire: the client answers the wizard from the link, signed out.
    await page.getByRole('link', { name: 'Questionnaire', exact: true }).click();
    await page.getByRole('button', { name: 'Send questionnaire link' }).click();
    const link = await page.getByTestId('questionnaire-link').inputValue();
    await page.getByRole('button', { name: 'Done' }).click();
    const clientView = await browser.newContext({ storageState: SIGNED_OUT });
    const client = await clientView.newPage();
    await client.goto(new URL(link).pathname);
    await expect(client.getByText(`Onboarding questionnaire for ${name}`)).toBeVisible();
    await client.getByRole('checkbox', { name: 'Increase Organic Traffic' }).click();
    await client
      .getByLabel('Please describe your goals in detail')
      .fill('40% more organic traffic');
    await client.getByRole('button', { name: 'Next' }).click();
    await client.getByLabel('Target locations').fill('India, UAE');
    await client.getByLabel('Target audiences').fill('Procurement managers');
    await client.getByRole('button', { name: 'Next' }).click();
    await client.getByLabel('Competitor 1', { exact: true }).fill('WidgetCo');
    await client.getByRole('button', { name: 'Save Draft' }).click();
    await expect(client.getByText('Draft saved.')).toBeVisible();
    await client.getByRole('button', { name: 'Next' }).click();
    await client.getByRole('checkbox', { name: 'Professional' }).click();
    await client.getByRole('button', { name: 'Next' }).click();
    await client
      .getByRole('group', { name: 'Has SEO been done on the website before?' })
      .getByLabel('Yes')
      .check();
    await client.getByRole('button', { name: 'Next' }).click();
    await client.getByRole('button', { name: 'Next' }).click();
    await expect(client.getByText('All required answers are in.')).toBeVisible();
    await shot(client, '04-questionnaire-summary');
    await client.getByRole('button', { name: 'Send answers' }).click();
    await expect(client.getByText('Your answers have been sent')).toBeVisible();
    await client.goto(new URL(link).pathname);
    await expect(client.getByText('invalid, already used or has expired')).toBeVisible();
    await clientView.close();
    await page.reload();
    await expect(page.getByText('Submitted', { exact: true })).toBeVisible();

    // 6–7. Access: request, receive, verify each.
    await page.getByRole('link', { name: 'Access', exact: true }).click();
    await page.getByRole('button', { name: 'Request Access' }).click();
    await expect(page.getByTestId('access-table').getByText('Requested').first()).toBeVisible();
    await page.getByRole('button', { name: 'Mark all received' }).click();
    for (const platform of [
      'Google Search Console',
      'Google Analytics 4',
      'CMS Access',
      'Ahrefs Account',
      'Google Drive Access',
    ]) {
      await page.getByRole('button', { name: `Actions for ${platform}` }).click();
      await page.getByRole('menuitem', { name: 'Verify' }).click();
      await expect(
        page
          .getByTestId('access-table')
          .getByRole('row')
          .filter({ hasText: platform })
          .getByText('Verified'),
      ).toBeVisible();
    }
    await expect(page.getByTestId('access-progress').getByText('100%')).toBeVisible();
    await shot(page, '05-access');

    // 8. KPI target + client confirmation.
    await page.getByRole('link', { name: 'KPIs', exact: true }).click();
    await page.getByRole('button', { name: 'Add KPI Target' }).click();
    const kpi = page.getByRole('dialog', { name: 'Add KPI target' });
    await kpi.getByLabel('Metric *').fill('Organic Sessions');
    await kpi.getByLabel('Baseline *').fill('10000');
    await kpi.getByLabel('Target *').fill('14000');
    await kpi.getByLabel('Unit *').fill('/ month');
    await kpi.getByRole('button', { name: 'Save' }).click();
    await expect(kpi).toBeHidden();
    await expect(page.getByTestId('kpi-table').getByText('Organic Sessions')).toBeVisible();
    await page.getByLabel('Confirmed by (client)').fill('Pat Buyer');
    await page.getByRole('button', { name: 'Record confirmation' }).click();
    await expect(page.getByTestId('kpis-confirmed')).toBeVisible();
    await shot(page, '06-kpis');

    // 10. Team.
    await page.getByRole('link', { name: 'Team', exact: true }).click();
    await page.getByRole('button', { name: 'Assign Member' }).click();
    const member = page.getByRole('dialog', { name: 'Assign team member' });
    await member.getByLabel('Team member *').selectOption({ label: 'E2E Flows' });
    await member.getByLabel('Service area').selectOption({ label: 'SEO' });
    await member.getByLabel('Role on this account').fill('SEO Specialist');
    await member.getByRole('button', { name: 'Assign' }).click();
    await expect(page.getByTestId('team-table').getByText('SEO Specialist')).toBeVisible();

    // 9–10. Kickoff call and internal kickoff are meetings, completed with notes.
    await page.getByRole('link', { name: 'Meetings', exact: true }).click();
    for (const [type, title] of [
      ['Kickoff', 'Kickoff Call'],
      ['Internal', 'Internal Kickoff'],
    ] as const) {
      await page.getByRole('button', { name: 'Schedule Meeting' }).click();
      const drawer = page.getByRole('dialog', { name: 'Schedule meeting' });
      await drawer.getByLabel('Title *').fill(title);
      await drawer.getByLabel('Type').selectOption({ label: type });
      await drawer.getByLabel('Start *').fill('00:00');
      await drawer.getByLabel('End *').fill('00:30');
      await drawer.getByRole('button', { name: 'Schedule meeting' }).click();
      await expect(page.getByText('Meeting scheduled.')).toBeVisible();
      const detail = page.getByTestId('meeting-detail');
      await expect(detail.getByRole('heading', { name: title })).toBeVisible();
      await detail.getByRole('button', { name: 'Complete with notes' }).click();
      await page.getByLabel('Meeting notes *').fill('Goals agreed\nNext: access review');
      await page.getByRole('button', { name: 'Mark completed' }).click();
      await expect(detail.getByText('Goals agreed')).toBeVisible();
    }

    await shot(page, '07-meetings');
    // 11–12. Review and completion from the overview.
    await page.getByRole('link', { name: 'Overview', exact: true }).click();
    await page.getByRole('button', { name: 'Pass onboarding review' }).click();
    await expect(page.getByRole('button', { name: 'Review passed ✓' })).toBeVisible();
    await page.getByRole('button', { name: 'Complete onboarding' }).click();
    await expect(page.getByText(/^Onboarding completed \d/)).toBeVisible();
    await expect(onboarding.getByText('92%')).toBeVisible();
    await expect(page.getByRole('heading', { level: 1 }).getByText('Active')).toBeVisible();
    await shot(page, '03b-client-profile-complete');

    // The board shows it as completed.
    await page.goto('/onboarding');
    const row = page.getByTestId('onboarding-board').getByRole('row').filter({ hasText: name });
    await expect(row.getByText('Completed')).toBeVisible();

    // 13. The first project, from the template, from the client overview.
    await page.goto(clientPath);
    await page.getByRole('link', { name: 'Create the delivery project →' }).click();
    await expect(page.getByLabel('Project name')).toHaveValue(`${name} SEO Retainer`);
    await page.getByLabel('Project manager').selectOption({ label: 'E2E Admin' });
    await page.getByRole('button', { name: 'Create project' }).click();
    await expect(
      page.getByRole('heading', { level: 1, name: `${name} SEO Retainer` }),
    ).toBeVisible();
    const board = page.getByTestId('task-board');
    const backlog = board.getByRole('region', { name: 'Backlog' });
    await expect(backlog.getByRole('button')).toHaveCount(5);
    await expect(backlog.getByText(/E2E Flows/)).toHaveCount(5);

    // Review-required work can be started but not completed directly.
    await backlog.getByRole('button', { name: /Keyword research/ }).click();
    const research = page.getByRole('dialog', { name: 'Keyword research' });
    await research.getByRole('button', { name: 'Start work' }).click();
    await expect(research.getByText('In progress', { exact: true })).toBeVisible();
    await expect(research.getByRole('button', { name: 'Mark completed' })).toHaveCount(0);
    await expect(research.getByText(/can't be marked completed directly/)).toBeVisible();
    await research.getByRole('button', { name: 'Close' }).click();
    await expect(
      board.getByRole('region', { name: 'In progress' }).getByRole('button'),
    ).toHaveCount(1);

    // A task without review: create, start, complete.
    await page.getByRole('button', { name: 'New task' }).click();
    const newTask = page.getByRole('dialog', { name: 'New task' });
    await newTask.getByLabel('Title').fill('Fix broken links');
    await newTask.getByLabel('Assignee').selectOption({ label: 'E2E Admin' });
    await newTask.getByLabel('Requires internal review').uncheck();
    await newTask.getByRole('button', { name: 'Create task' }).click();
    const fix = page.getByRole('dialog', { name: 'Fix broken links' });
    await fix.getByRole('button', { name: 'Start work' }).click();
    await fix.getByRole('button', { name: 'Mark completed' }).click();
    await expect(fix.getByText('Completed', { exact: true }).first()).toBeVisible();
    await fix.getByRole('button', { name: 'Close' }).click();
    await expect(page.getByTestId('project-stats').getByText('17%')).toBeVisible(); // 1 of 6

    // Review: submit v1, changes requested (feedback required), v2 approved → completed.
    await board.getByRole('button', { name: /Keyword research/ }).click();
    await research.getByRole('button', { name: 'Submit for review' }).click();
    await research.getByLabel('What changed / notes for the reviewer').fill('First keyword list');
    await research.getByLabel('Link to the work').fill('https://docs.example.com/keywords');
    await research.getByRole('button', { name: 'Submit v1' }).click();
    await expect(research.getByText('Awaiting internal review · v1')).toBeVisible();
    await research.getByRole('button', { name: 'Request changes' }).click();
    await expect(page.getByText('Add feedback explaining the requested changes.')).toBeVisible();
    await research.getByLabel(/^Feedback/).fill('Add search volumes');
    await research.getByRole('button', { name: 'Request changes' }).click();
    await expect(research.getByText('In progress', { exact: true })).toBeVisible();
    await expect(research.getByText('Add search volumes')).toBeVisible();
    await research.getByRole('button', { name: 'Submit for review' }).click();
    await research.getByLabel('What changed / notes for the reviewer').fill('Volumes added');
    await research.getByRole('button', { name: 'Submit v2' }).click();
    await research.getByRole('button', { name: 'Approve' }).click();
    await expect(research.getByText('Completed', { exact: true }).first()).toBeVisible();
    await research.getByRole('button', { name: 'Close' }).click();

    // A task that also needs the client: internal approval, then the client's decision.
    await board.getByRole('button', { name: /Technical fixes roadmap/ }).click();
    const roadmap = page.getByRole('dialog', { name: 'Technical fixes roadmap' });
    await roadmap.getByRole('button', { name: 'Start work' }).click();
    await roadmap.getByRole('button', { name: 'Submit for review' }).click();
    await roadmap.getByLabel('What changed / notes for the reviewer').fill('Roadmap draft');
    await roadmap.getByRole('button', { name: 'Submit v1' }).click();
    await roadmap.getByRole('button', { name: 'Approve' }).click();
    await expect(roadmap.getByText('Awaiting client approval · v1')).toBeVisible();
    await expect(roadmap.getByLabel('Client decision-maker')).toHaveValue('Pat Buyer');
    await roadmap.getByLabel('Communicated via').selectOption({ label: 'Call' });
    await roadmap.getByRole('button', { name: 'Approve' }).click();
    await expect(roadmap.getByText('Pat Buyer (client, via a call)')).toBeVisible();
    await roadmap.getByRole('button', { name: 'Close' }).click();
    await expect(page.getByTestId('project-stats').getByText('50%')).toBeVisible(); // 3 of 6

    await page.goto('/approvals');
    const requests = page.getByTestId('approvals-all');
    await expect(
      requests.getByRole('row').filter({ hasText: 'Technical fixes roadmap' }),
    ).toHaveCount(2);
    await expect(requests.getByText('Changes requested')).toBeVisible();

    // My open work lists the specialist's queue on /tasks; the project is listed.
    await page.goto('/tasks?view=all');
    await expect(
      page.getByTestId('task-table').getByText('Baseline SEO audit').first(),
    ).toBeVisible();
    await page.goto('/projects');
    await expect(
      page.getByTestId('projects-table').getByText(`${name} SEO Retainer`),
    ).toBeVisible();

    // Onboarding is now 100%.
    await page.goto(clientPath);
    await expect(onboarding.getByText('100%')).toBeVisible();
  });
});

test.describe('people and organization settings', () => {
  test.use({ storageState: AUTH_FILE });

  test('employees, reporting lines with preview, org chart, roles and audit log', async ({
    page,
  }) => {
    test.setTimeout(180_000);
    const stamp = Date.now();
    const lead = `Mei Lead ${stamp}`;
    const member = `Jordan Blake ${stamp}`;

    // The nine departments exist from the start, with their purposes.
    await page.goto('/team/teams?tab=departments');
    const departments = page.getByTestId('departments-table');
    for (const name of [
      'Content Team',
      'Design Team',
      'SEO Team',
      'Social Media Team',
      'Performance Marketing Team',
      'Web Development Team',
      'Application Development Team',
      'Project Management Team',
      'Operations Team',
    ]) {
      await expect(departments.getByRole('link', { name, exact: true })).toBeVisible();
    }
    await shot(page, 'org-departments');

    // An SEO manager, then a specialist reporting to them.
    await page.goto('/team/employees/new');
    await page.getByLabel('Full legal name *').fill(lead);
    await page.getByLabel('Department').selectOption({ label: 'SEO Team' });
    await page.getByLabel('Designation').selectOption({ label: 'SEO Manager' });
    await page.getByLabel('Employment status').selectOption({ label: 'Active' });
    await page.getByRole('button', { name: 'Create employee' }).click();
    await expect(page.getByRole('heading', { level: 1 }).getByText(lead)).toBeVisible();
    await expect(page.getByText(/^DD-\d{4}/).first()).toBeVisible();

    await page.goto('/team/employees/new');
    await page.getByLabel('Full legal name *').fill(member);
    await page.getByLabel('Official e-mail').fill(`jordan-${stamp}@delphin.example`);
    await page.getByLabel('Department').selectOption({ label: 'SEO Team' });
    await page.getByLabel('Designation').selectOption({ label: 'SEO Executive' });
    await pickOption(page.getByLabel('Direct manager'), lead);
    await page.getByLabel('Work arrangement').selectOption({ label: 'Hybrid' });
    await page.getByRole('button', { name: 'Create employee' }).click();
    await expect(page.getByRole('heading', { level: 1 }).getByText(member)).toBeVisible();
    await expect(page.getByRole('link', { name: lead }).first()).toBeVisible();

    // Employment: every relationship that applies; a status change is recorded.
    await page.getByRole('tab', { name: 'Employment' }).click();
    const relations = page.locator('section').filter({ hasText: 'Reporting relationships' });
    await expect(relations.getByText('Direct manager:')).toBeVisible();
    await expect(relations.getByText('Leave approver:')).toBeVisible();
    await expect(relations.getByText('(via the direct manager)').first()).toBeVisible();
    await page.getByRole('button', { name: 'Edit employment' }).click();
    await page.getByLabel('Employment status').selectOption({ label: 'On probation' });
    await page.getByRole('button', { name: 'Save employment' }).click();
    await expect(page.getByText('Employment updated.')).toBeVisible();
    await page.getByRole('tab', { name: 'Activity' }).click();
    await expect(page.getByText('Status: Onboarding → On probation')).toBeVisible();

    // Personal details (HR may edit them too).
    await page.getByRole('tab', { name: 'Personal' }).click();
    await page.getByRole('button', { name: 'Edit personal details' }).click();
    await page.getByLabel('Emergency contact').fill('Alex Blake');
    await page.getByLabel('Emergency phone').fill('+91 98450 11111');
    await page.getByRole('button', { name: 'Save personal details' }).click();
    await expect(page.getByText('Alex Blake')).toBeVisible();

    // Make the manager head of the SEO Team.
    await page.goto('/team/teams?tab=departments');
    await page.getByRole('button', { name: 'Edit SEO Team' }).click();
    const dialog = page.getByRole('dialog', { name: 'Edit SEO Team' });
    await pickOption(dialog.getByLabel('Department head'), lead);
    await dialog.getByRole('button', { name: 'Save' }).click();
    const seoRow = departments.getByRole('row').filter({ hasText: 'SEO Team' });
    await expect(seoRow.getByText(lead)).toBeVisible();

    // Reporting: add a functional manager, preview the impact, then save.
    await page.goto('/team/teams?tab=reporting');
    await pickOption(page.getByLabel('Employee', { exact: true }), member);
    await expect(page.getByText('What applies now')).toBeVisible();
    await page.getByRole('button', { name: 'Add relationship' }).click();
    await page.getByLabel('Relationship 2', { exact: true }).selectOption({ label: 'Performance reviewer' });
    await pickOption(page.getByLabel('Reports to').nth(1), lead);
    await expect(page.getByRole('button', { name: 'Save changes' })).toBeDisabled();
    await page.getByRole('button', { name: 'Preview changes' }).click();
    const preview = page.getByTestId('reporting-preview');
    await expect(preview.getByText(`Performance reviewer: ${lead}`).first()).toBeVisible();
    await expect(preview.getByTestId('chart-preview')).toBeVisible();
    await shot(page, 'org-reporting-preview');
    await page.getByRole('button', { name: 'Save changes' }).click();
    await expect(page.getByText(`Reporting for ${member} saved.`)).toBeVisible();
    await expect(
      page.getByTestId('reporting-history').getByText('Performance reviewer'),
    ).toBeVisible();

    // A loop is refused before anything is saved.
    await pickOption(page.getByLabel('Employee', { exact: true }), lead);
    await expect(page.getByText(`Edit relationships: ${lead}`)).toBeVisible();
    await page.getByRole('button', { name: 'Add relationship' }).click();
    await pickOption(page.getByLabel('Reports to').last(), member);
    await page.getByRole('button', { name: 'Preview changes' }).click();
    await expect(page.getByText(/That would create a reporting loop/)).toBeVisible();
    await expect(page.getByRole('button', { name: 'Save changes' })).toBeDisabled();

    // Org chart: executive and delivery views, labelled lines, filters.
    await page.goto('/team/teams');
    const chart = page.getByTestId('org-chart');
    const seo = chart.getByRole('region', { name: 'SEO Team' });
    await expect(seo.getByRole('link', { name: member })).toBeVisible();
    await expect(seo.getByText('Direct manager:').first()).toBeVisible();
    await page.getByLabel('Reporting type').selectOption({ label: 'Performance reviewer' });
    await expect(seo.getByText('Performance reviewer:')).toBeVisible();
    await shot(page, 'org-chart');
    await page.getByRole('tab', { name: 'Project delivery' }).click();
    await shot(page, 'org-delivery');

    // Roles: the matrix, and a new role limited to the organisation module.
    await page.goto('/team/teams?tab=roles');
    await expect(page.getByTestId('permission-matrix')).toBeVisible();
    await page.getByRole('button', { name: 'New role' }).click();
    const roleDialog = page.getByRole('dialog', { name: 'New role' });
    await roleDialog.getByLabel('Key *').fill(`viewer_${stamp}`);
    await roleDialog.getByLabel('Name *').fill(`Org Viewer ${stamp}`);
    await roleDialog.getByLabel('View organization structure').check();
    await roleDialog.getByRole('button', { name: 'Save role' }).click();
    await expect(page.getByText(`Role Org Viewer ${stamp} created.`)).toBeVisible();
    await expect(
      page.getByTestId('permission-matrix').getByText(`Org Viewer ${stamp}`, { exact: true }),
    ).toBeVisible();
    await shot(page, 'org-roles');

    // Audit log.
    await page.goto('/team/teams?tab=audit');
    const audit = page.getByTestId('org-audit');
    await expect(audit.getByText('Reporting changed').first()).toBeVisible();
    await expect(audit.getByText('Role created').first()).toBeVisible();
    await shot(page, 'org-audit');

    // Directory search.
    await page.goto('/team/employees');
    await page.getByLabel('Search').fill(`jordan-${stamp}`);
    const table = page.getByTestId('employees-table');
    await expect(table.getByRole('row')).toHaveCount(2); // header + Jordan
    await expect(table.getByText('On probation')).toBeVisible();
  });
});

/** Select the option whose text contains `text` (labels like "Name (DD-0007)"). */
async function pickOption(select: Locator, text: string) {
  const value = await select.locator('option', { hasText: text }).first().getAttribute('value');
  await select.selectOption(value ?? '');
}

/** Full-page screenshot for visual review against the mockups (test-results/screens). */
async function shot(page: Page, name: string) {
  await page.waitForLoadState('networkidle');
  await page.screenshot({ path: `test-results/screens/${name}.png`, fullPage: true });
}
