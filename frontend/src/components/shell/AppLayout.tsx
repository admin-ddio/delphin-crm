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
import { useAuth } from '@/lib/auth-context';

export function AppLayout() {
  const { status } = useAuth();
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);

  if (status === 'unknown') return null;
  if (status === 'anonymous') {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  return (
    <div className="min-h-full shell:grid shell:grid-cols-[228px_minmax(0,1fr)]">
      <DocumentTitle />
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded-md focus:bg-surface focus:px-3 focus:py-2 focus:shadow"
      >
        Skip to main content
      </a>
      <Sidebar mobileOpen={mobileOpen} onNavigate={() => setMobileOpen(false)} />
      {mobileOpen ? (
        <button
          type="button"
          aria-label="Close menu"
          className="fixed inset-0 z-30 bg-[rgb(8_20_26/.45)] shell:hidden"
          onClick={() => setMobileOpen(false)}
        />
      ) : null}
      <div className="flex min-w-0 flex-col">
        <Topbar mobileOpen={mobileOpen} onToggleMenu={() => setMobileOpen((open) => !open)} />
        <main
          id="main"
          tabIndex={-1}
          className="w-full max-w-[1320px] px-4 pt-[22px] pb-[60px] focus:outline-none"
        >
          <Suspense fallback={null}>
            <Outlet />
          </Suspense>
        </main>
      </div>
    </div>
  );
}
