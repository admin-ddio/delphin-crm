import { expect, test } from '@playwright/test';

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

  test('the app reaches the API and receives a CSRF cookie', async ({ page, context }) => {
    await page.goto('/dashboard');
    await expect(page.getByTestId('api-status')).toHaveText('API connected');
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

    await page.getByRole('button', { name: 'Sign out' }).click();
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

test.describe('clients', () => {
  test.use({ storageState: AUTH_FILE });

  test('create, duplicate rules, search, view, edit and activity', async ({ page }) => {
    const stamp = Date.now();
    const name = `Playwright Widgets ${stamp}`;
    const domain = `pw-widgets-${stamp}.example`;

    // Create.
    await page.goto('/clients');
    await page.getByRole('link', { name: 'New client' }).click();
    await expect(page.getByRole('heading', { level: 1, name: 'New client' })).toBeVisible();
    await page.getByLabel('Legal / business name *').fill(name);
    await page.getByLabel('Website').fill(`https://www.${domain}/home`);
    await page.getByLabel('Industry').fill('Manufacturing');
    await page.getByLabel('Primary contact').fill('Pat Buyer');
    await page.getByLabel('Contact e-mail').fill('pat@example.com');
    await page.getByLabel('Account Manager *').selectOption({ label: 'E2E Admin' });
    await page.getByRole('button', { name: 'Create client' }).click();

    await expect(page.getByRole('heading', { level: 1 })).toContainText(name);
    await expect(page.getByText(/^CL-\d{4}$/)).toBeVisible();
    await expect(page.getByText('Contract pending').first()).toBeVisible();
    const clientUrl = page.url();

    // Same domain: hard block, even when "different business" is ticked.
    await page.goto('/clients/new');
    await page.getByLabel('Legal / business name *').fill(`Unrelated ${stamp}`);
    await page.getByLabel('Website').fill(domain);
    await page.getByLabel('Account Manager *').selectOption({ label: 'E2E Admin' });
    await page.getByLabel(/This is a different business/).check();
    await page.getByRole('button', { name: 'Create client' }).click();
    await expect(page.getByRole('alert')).toContainText(`domain ${domain} already exists`);

    // Similar name: warning until confirmed.
    await page.getByLabel('Legal / business name *').fill(`${name} Ltd.`);
    await page.getByLabel('Website').fill('');
    await page.getByLabel(/This is a different business/).uncheck();
    await page.getByRole('button', { name: 'Create client' }).click();
    await expect(page.getByText('Possible duplicate')).toBeVisible();
    await page.getByLabel(/This is a different business/).check();
    await page.getByRole('button', { name: 'Create client' }).click();
    await expect(page.getByRole('heading', { level: 1 })).toContainText(`${name} Ltd.`);

    // Search the list.
    await page.goto('/clients');
    await page.getByLabel('Search').fill(domain);
    const table = page.getByTestId('clients-table');
    await expect(table.getByRole('link', { name, exact: true })).toBeVisible();
    await expect(table.getByRole('row')).toHaveCount(2); // header + 1 match

    // Edit, then see it in the activity log.
    await page.goto(clientUrl);
    await page.getByRole('link', { name: 'Edit client' }).click();
    await page.getByLabel('Industry').fill('Retail');
    await page.getByRole('button', { name: 'Save changes' }).click();
    await expect(page.getByText('Client updated.')).toBeVisible();
    await expect(page.getByText('Retail')).toBeVisible();

    await page.getByRole('link', { name: 'Activity', exact: true }).click();
    await expect(page.getByText('Client details updated: industry')).toBeVisible();
    await expect(page.getByText(`Client ${name} created`)).toBeVisible();

    // Tabs that aren't ported yet say so inside the client layout.
    await page.getByRole('link', { name: 'Billing', exact: true }).click();
    await expect(page.getByText("Billing isn't ported yet")).toBeVisible();
  });
});
