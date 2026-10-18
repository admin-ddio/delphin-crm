import { useEffect } from 'react';
import { useMatches } from 'react-router';

import type { RouteHandle } from '@/app/placeholder-route';

/** Suffix from the clickable demo's window title. TODO(pilot-port): match the pilot's metadata. */
const SUFFIX = 'Delphin Agency Console';

export function DocumentTitle() {
  const matches = useMatches();
  const handle = [...matches].reverse().find((match) => (match.handle as RouteHandle | undefined)?.title)
    ?.handle as RouteHandle | undefined;
  const title = handle ? `${handle.title} · ${SUFFIX}` : SUFFIX;

  useEffect(() => {
    document.title = title;
  }, [title]);

  return null;
}
