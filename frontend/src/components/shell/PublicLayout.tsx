/**
 * Unauthenticated card layout (sign-in, password reset, activation).
 * PROVISIONAL markup (the demo has no sign-in page). Port from the pilot's auth
 * pages and match 00-login.png.
 */
import { Outlet } from 'react-router';

import { DocumentTitle } from '@/components/shell/DocumentTitle';

export function PublicLayout() {
  return (
    <div className="flex min-h-full items-center justify-center px-4 py-12">
      <DocumentTitle />
      <main id="main" className="card w-full max-w-sm p-8">
        <div className="mb-6 flex items-center gap-2.5">
          <span
            aria-hidden
            className="grid size-[30px] place-items-center rounded-[7px] bg-accent font-bold text-on-accent"
          >
            D
          </span>
          <div>
            <b className="block text-sm leading-[1.1]">Delphin Digital</b>
            <small className="block text-[11px] text-muted">Agency console</small>
          </div>
        </div>
        <Outlet />
      </main>
    </div>
  );
}

/** No chrome at all: the public client questionnaire (/q/:token). */
export function BareLayout() {
  return (
    <main id="main" className="mx-auto max-w-3xl px-4 py-10">
      <DocumentTitle />
      <Outlet />
    </main>
  );
}
