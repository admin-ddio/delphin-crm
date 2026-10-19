/**
 * Signed-in shell: skip link, left rail, top bar, main content (max 1320 px).
 * Grid layout from the clickable demo: 228 px rail + fluid main from 861 px up;
 * below that the rail is an off-canvas drawer opened by "Menu".
 */
import { Suspense, useState } from 'react';
import { Navigate, Outlet, useLocation } from 'react-router';

import { DocumentTitle } from '@/components/shell/DocumentTitle';
import { Sidebar } from '@/components/shell/Sidebar';
import { Topbar } from '@/components/shell/Topbar';
import { useApprovals } from '@/features/approvals/api';
import { useTasks } from '@/features/tasks/api';
import { useAuth } from '@/lib/auth-context';

/** The rail with its live counters (my open tasks, requests waiting for my decision). */
function CountedSidebar(props: { mobileOpen: boolean; onNavigate(): void }) {
  const tasks = useTasks('mine');
  const approvals = useApprovals('mine');
  return (
    <Sidebar
      {...props}
      badgeCounts={{
        myOpenTasks: tasks.data?.length,
        myPendingApprovals: approvals.data?.length,
      }}
    />
  );
}

export function AppLayout() {
  const { status } = useAuth();
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);

  if (status === 'unknown') return null;
  if (status === 'anonymous') {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  return (
    <div className="min-h-full shell:grid shell:grid-cols-[248px_minmax(0,1fr)]">
      <DocumentTitle />
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded-md focus:bg-surface focus:px-3 focus:py-2 focus:shadow"
      >
        Skip to main content
      </a>
      <CountedSidebar mobileOpen={mobileOpen} onNavigate={() => setMobileOpen(false)} />
      {mobileOpen ? (
        <button
          type="button"
          aria-label="Close menu"
          className="fixed inset-0 z-30 bg-[rgb(14_18_64/.5)] shell:hidden"
          onClick={() => setMobileOpen(false)}
        />
      ) : null}
      <div className="flex min-w-0 flex-col">
        <Topbar mobileOpen={mobileOpen} onToggleMenu={() => setMobileOpen((open) => !open)} />
        <main
          id="main"
          tabIndex={-1}
          className="w-full max-w-[1440px] px-4 pt-2 pb-[60px] focus:outline-none shell:px-8"
        >
          <Suspense fallback={null}>
            <Outlet />
          </Suspense>
        </main>
      </div>
    </div>
  );
}
