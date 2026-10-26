import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { describe, expect, it } from 'vitest';

import { routes } from '@/app/router';
import { PlaceholderPage } from '@/components/PlaceholderPage';
import { Button } from '@/components/ui/Button';
import { EmptyState } from '@/components/ui/EmptyState';
import { PageHeader } from '@/components/ui/PageHeader';
import { ToastProvider, useToast } from '@/components/ui/Toast';
import { AuthProvider, type Actor } from '@/lib/auth-context';

const superAdmin: Actor = {
  id: 'u1',
  email: 'admin@example.test',
  fullName: 'Ada Admin',
  roles: ['super_admin'],
  permissions: ['*'],
};

function renderAt(path: string, actor: Actor | null = superAdmin) {
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <AuthProvider initialActor={actor}>
        <ToastProvider>
          <RouterProvider router={router} />
        </ToastProvider>
      </AuthProvider>
    </QueryClientProvider>,
  );
}

describe('primitives', () => {
  it('PageHeader renders a level-1 heading and actions', () => {
    render(<PageHeader title="Clients" description="All clients" actions={<Button>New</Button>} />);
    expect(screen.getByRole('heading', { level: 1, name: 'Clients' })).toBeInTheDocument();
    expect(screen.getByText('All clients')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'New' })).toHaveAttribute('type', 'button');
  });

  it('EmptyState renders title and description', () => {
    render(<EmptyState title="Nothing" description="Yet" />);
    expect(screen.getByText('Nothing')).toBeInTheDocument();
    expect(screen.getByText('Yet')).toBeInTheDocument();
  });

  it('PlaceholderPage points at PARITY.md', () => {
    render(<PlaceholderPage title="Finance" module="finance" />);
    expect(screen.getByRole('heading', { level: 1, name: 'Finance' })).toBeInTheDocument();
    expect(screen.getByText('Not yet ported. See PARITY.md')).toBeInTheDocument();
  });

  it('toasts announce politely and can be dismissed', async () => {
    function Trigger() {
      const { toast } = useToast();
      return <Button onClick={() => toast({ title: 'Saved', durationMs: 0 })}>Go</Button>;
    }
    render(
      <ToastProvider>
        <Trigger />
      </ToastProvider>,
    );
    await userEvent.click(screen.getByRole('button', { name: 'Go' }));
    expect(screen.getByRole('status')).toHaveTextContent('Saved');
    await userEvent.click(screen.getByRole('button', { name: 'Dismiss' }));
    expect(screen.queryByText('Saved')).not.toBeInTheDocument();
  });
});

describe('app shell', () => {
  it('renders a placeholder route inside the shell', async () => {
    renderAt('/clients');
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Client List' }),
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Skip to main content' })).toHaveAttribute(
      'href',
      '#main',
    );
    const nav = screen.getByRole('navigation', { name: 'Main' });
    expect(within(nav).getByRole('link', { name: 'CRM & Clients' })).toHaveAttribute(
      'aria-current',
      'page',
    );
  });

  it('redirects anonymous visitors to sign in', async () => {
    renderAt('/dashboard', null);
    expect(await screen.findByRole('heading', { level: 1, name: 'Sign in' })).toBeInTheDocument();
  });

  it('redirects / to the dashboard', async () => {
    renderAt('/');
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Good day, Ada' }),
    ).toBeInTheDocument();
  });

  it('shows not found for unknown paths', async () => {
    renderAt('/no-such-page');
    expect(await screen.findByText('Page not found')).toBeInTheDocument();
  });

  it('toggles the mobile menu', async () => {
    renderAt('/dashboard');
    const toggle = await screen.findByRole('button', { name: 'Menu' });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    await userEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
  });
});
