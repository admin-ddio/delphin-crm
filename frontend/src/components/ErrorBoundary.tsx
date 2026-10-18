import { Component, type ErrorInfo, type ReactNode } from 'react';
import { isRouteErrorResponse, useRouteError } from 'react-router';

import { Alert } from '@/components/ui/Alert';
import { EmptyState } from '@/components/ui/EmptyState';
import { LinkButton } from '@/components/ui/Button';
import { ApiError } from '@/lib/api-client';

function describe(error: unknown): { title: string; detail?: string } {
  if (isRouteErrorResponse(error)) {
    return error.status === 404
      ? { title: 'Page not found' }
      : { title: `Error ${error.status}`, detail: error.statusText };
  }
  if (error instanceof ApiError) {
    return {
      title: error.message,
      detail: error.requestId ? `Reference: ${error.requestId}` : undefined,
    };
  }
  return { title: 'Something went wrong' };
}

/** errorElement for the route tree. Never shows stack traces. */
export function RouteErrorBoundary() {
  const { title, detail } = describe(useRouteError());
  return (
    <main id="main" className="mx-auto max-w-lg px-4 py-16">
      <Alert tone="bad" title={title}>
        {detail}
      </Alert>
      <div className="mt-6">
        <LinkButton to="/dashboard" variant="secondary">
          Back to dashboard
        </LinkButton>
      </div>
    </main>
  );
}

export function NotFoundPage() {
  return (
    <main id="main" className="mx-auto max-w-lg px-4 py-16">
      <EmptyState
        title="Page not found"
        action={
          <LinkButton to="/dashboard" variant="secondary">
            Back to dashboard
          </LinkButton>
        }
      />
    </main>
  );
}

interface AppErrorBoundaryState {
  failed: boolean;
}

/** Last-resort boundary around the providers (route errors are handled by the router). */
export class AppErrorBoundary extends Component<{ children: ReactNode }, AppErrorBoundaryState> {
  state: AppErrorBoundaryState = { failed: false };

  static getDerivedStateFromError(): AppErrorBoundaryState {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('Unhandled UI error', error, info.componentStack);
  }

  render() {
    if (this.state.failed) {
      return (
        <main id="main" className="mx-auto max-w-lg px-4 py-16">
          <Alert tone="bad" title="Something went wrong">
            Reload the page to continue.
          </Alert>
        </main>
      );
    }
    return this.props.children;
  }
}
