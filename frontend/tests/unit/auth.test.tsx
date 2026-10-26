import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { describe, expect, it, vi } from 'vitest';

import { routes } from '@/app/router';
import { ToastProvider } from '@/components/ui/Toast';
import { ApiError } from '@/lib/api-client';
import * as authContext from '@/lib/auth-context';
import { EmailNotVerifiedError, type Actor, type AuthState } from '@/lib/auth-context';

const ada: Actor = {
  id: 'u1',
  email: 'ada@example.com',
  fullName: 'Ada Lovelace',
  roles: ['account_manager'],
  permissions: ['clients.create'],
};

function renderAt(path: string, auth: Partial<AuthState>) {
  const state: AuthState = {
    status: 'anonymous',
    actor: null,
    signIn: vi.fn(),
    signOut: vi.fn(),
    resendVerification: vi.fn(),
    ...auth,
  };
  // A live object, so tests can flip it the way the real context does after sign-in/out.
  vi.spyOn(authContext, 'useAuth').mockImplementation(() => state);
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <ToastProvider>
        <RouterProvider router={router} />
      </ToastProvider>
    </QueryClientProvider>,
  );
  return { state, router };
}

describe('sign in', () => {
  it('validates before calling the API', async () => {
    const { state } = renderAt('/login', {});
    await userEvent.click(await screen.findByRole('button', { name: 'Sign in' }));
    expect(await screen.findByText('Enter a valid e-mail address.')).toBeInTheDocument();
    expect(screen.getByText('Enter your password.')).toBeInTheDocument();
    expect(screen.getByLabelText('Email')).toHaveAttribute('aria-invalid', 'true');
    expect(state.signIn).not.toHaveBeenCalled();
  });

  it('shows the API message when sign-in fails', async () => {
    const signIn = vi.fn().mockRejectedValue(
      new ApiError(401, {
        code: 'unauthorized',
        message: 'Invalid email or password.',
        details: {},
        request_id: 'r1',
      }),
    );
    renderAt('/login', { signIn });
    await userEvent.type(await screen.findByLabelText('Email'), 'ada@example.com');
    await userEvent.type(screen.getByLabelText('Password'), 'wrong');
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid email or password.');
    expect(signIn).toHaveBeenCalledWith('ada@example.com', 'wrong');
  });

  it('goes to the dashboard after signing in', async () => {
    const signIn = vi.fn();
    const { router, state } = renderAt('/login', { signIn });
    signIn.mockImplementation(async () => {
      Object.assign(state, { status: 'authenticated', actor: ada });
      return ada;
    });
    await userEvent.type(await screen.findByLabelText('Email'), 'ada@example.com');
    await userEvent.type(screen.getByLabelText('Password'), 'correct-horse-battery-staple');
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    await vi.waitFor(() => expect(router.state.location.pathname).toBe('/dashboard'));
  });

  it('offers to resend the verification e-mail', async () => {
    const resendVerification = vi.fn().mockResolvedValue(undefined);
    const signIn = vi.fn().mockRejectedValue(new EmailNotVerifiedError());
    renderAt('/login', { signIn, resendVerification });
    await userEvent.type(await screen.findByLabelText('Email'), 'ada@example.com');
    await userEvent.type(screen.getByLabelText('Password'), 'correct-horse-battery-staple');
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByText('Verify your e-mail address')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Resend verification e-mail' }));
    expect(resendVerification).toHaveBeenCalled();
    expect(await screen.findByText('Check your inbox.')).toBeInTheDocument();
  });

  it('links to sign-up from the login page', async () => {
    const { router } = renderAt('/login', {});
    expect(await screen.findByText("Don't have an account?")).toBeInTheDocument();
    await userEvent.click(screen.getByRole('link', { name: 'Sign up' }));
    await vi.waitFor(() => expect(router.state.location.pathname).toBe('/signup'));
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Create account' }),
    ).toBeInTheDocument();
  });

  it('explains when the account is waiting for approval', async () => {
    const signIn = vi.fn().mockRejectedValue(
      new ApiError(403, {
        code: 'pending_approval',
        message: 'Your account is waiting for approval by an administrator.',
        details: {},
        request_id: 'r2',
      }),
    );
    renderAt('/login', { signIn });
    await userEvent.type(await screen.findByLabelText('Email'), 'sam@example.com');
    await userEvent.type(screen.getByLabelText('Password'), 'correct-horse-battery-staple');
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByText('Waiting for approval')).toBeInTheDocument();
  });

  it('validates the sign-up form before calling Firebase', async () => {
    renderAt('/signup', {});
    await userEvent.type(await screen.findByLabelText('Email'), 'not-an-email');
    await userEvent.type(screen.getByLabelText('Password'), 'short');
    await userEvent.type(screen.getByLabelText('Confirm password'), 'different');
    await userEvent.click(screen.getByRole('button', { name: 'Create account' }));
    expect(await screen.findByText('Enter your full name.')).toBeInTheDocument();
    expect(screen.getByText('Enter a valid e-mail address.')).toBeInTheDocument();
    expect(screen.getByText('Use at least 12 characters.')).toBeInTheDocument();
    expect(screen.getByText("The passwords don't match.")).toBeInTheDocument();
  });

  it('skips the form when already signed in', async () => {
    const { router } = renderAt('/login', { status: 'authenticated', actor: ada });
    await vi.waitFor(() => expect(router.state.location.pathname).toBe('/dashboard'));
  });
});

describe('account', () => {
  it('shows the profile and checks the new password', async () => {
    renderAt('/account', { status: 'authenticated', actor: ada });
    expect(
      await screen.findByRole('heading', { level: 1, name: 'My account' }),
    ).toBeInTheDocument();
    expect(within(screen.getByRole('main')).getByText('Account Manager')).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText('Current password'), 'old-password');
    await userEvent.type(screen.getByLabelText('New password'), 'short');
    await userEvent.type(screen.getByLabelText('Confirm new password'), 'different');
    await userEvent.click(screen.getByRole('button', { name: 'Change password' }));
    expect(await screen.findByText('Use at least 12 characters.')).toBeInTheDocument();
    expect(screen.getByText("The passwords don't match.")).toBeInTheDocument();
  });

  it('signs out from the top bar', async () => {
    const signOut = vi.fn();
    const { router, state } = renderAt('/dashboard', {
      status: 'authenticated',
      actor: ada,
      signOut,
    });
    signOut.mockImplementation(async () => {
      Object.assign(state, { status: 'anonymous', actor: null });
    });
    expect(await screen.findByTestId('current-user')).toHaveTextContent('Ada Lovelace');
    await userEvent.click(screen.getByTestId('current-user'));
    await userEvent.click(screen.getByRole('menuitem', { name: 'Sign out' }));
    expect(signOut).toHaveBeenCalled();
    await vi.waitFor(() => expect(router.state.location.pathname).toBe('/login'));
  });
});
