/** Pure data describing one pilot route. No React imports: tests and Playwright read it. */

export const MODULE_KEYS = [
  'auth',
  'dashboard',
  'notifications',
  'clients',
  'onboarding',
  'projects',
  'tasks',
  'approvals',
  'meetings',
  'services',
  'seo',
  'content',
  'team',
  'documents',
  'reports',
  'finance',
  'search',
  'settings',
  'activity',
] as const;
export type ModuleKey = (typeof MODULE_KEYS)[number];

/** app = signed-in shell; public = sign-in style card; bare = no chrome (public questionnaire). */
export type RouteLayout = 'app' | 'public' | 'bare';

export interface RouteSpec {
  path: string;
  /** Page title rendered by <PageHeader>. */
  title: string;
  module: ModuleKey;
  layout: RouteLayout;
  /** Pilot screenshot baselines for this route (reference/pilot/screenshots). */
  screenshots?: readonly string[];
  /**
   * Where the title comes from. undefined = scaffold guess; 'demo' = the clickable
   * demo's h1 (low authority); 'pilot' = checked against the pilot's page.tsx.
   * TODO(pilot-port): every title must reach 'pilot'.
   */
  titleSource?: 'demo' | 'pilot';
  /** A real page renders here (its heading may be data, e.g. the client's name). */
  ported?: boolean;
}

/** Sample values used to visit parameterised routes in tests. */
export const SAMPLE_PARAMS: Record<string, string> = {
  id: '00000000-0000-0000-0000-000000000001',
  token: 'sample-token',
  csId: '00000000-0000-0000-0000-000000000002',
  clientId: '00000000-0000-0000-0000-000000000003',
};

export function samplePath(path: string): string {
  return path.replace(/:(\w+)/g, (_, name: string) => SAMPLE_PARAMS[name] ?? name);
}
