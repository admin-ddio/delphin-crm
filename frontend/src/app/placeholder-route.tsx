import type { RouteObject } from 'react-router';

import type { RouteLayout, RouteSpec } from '@/app/route-spec';

export interface RouteHandle {
  title: string;
  module: RouteSpec['module'];
}

/** A lazy route that renders the "not yet ported" page for `spec`. */
export function placeholderRoute(spec: RouteSpec): RouteObject {
  return {
    path: spec.path,
    handle: { title: spec.title, module: spec.module } satisfies RouteHandle,
    lazy: async () => {
      const { PlaceholderPage } = await import('@/components/PlaceholderPage');
      return {
        Component: function Placeholder() {
          return <PlaceholderPage title={spec.title} module={spec.module} />;
        },
      };
    },
  };
}

export type RoutesByLayout = Record<RouteLayout, RouteObject[]>;

export function groupByLayout(
  specs: readonly RouteSpec[],
  overrides: Partial<Record<string, RouteObject['lazy']>> = {},
): RoutesByLayout {
  const grouped: RoutesByLayout = { app: [], public: [], bare: [] };
  for (const spec of specs) {
    const route = placeholderRoute(spec);
    const lazy = overrides[spec.path];
    grouped[spec.layout].push(lazy ? { ...route, lazy } : route);
  }
  return grouped;
}
