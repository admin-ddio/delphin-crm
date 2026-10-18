import { describe, expect, it } from 'vitest';

import { MODULE_KEYS, samplePath } from '@/app/route-spec';
import { ALL_ROUTE_SPECS } from '@/app/routes';

describe('route inventory', () => {
  it('registers every pilot module', () => {
    const modules = new Set(ALL_ROUTE_SPECS.map((spec) => spec.module));
    expect([...modules].sort()).toEqual([...MODULE_KEYS].sort());
  });

  it('has unique paths', () => {
    const paths = ALL_ROUTE_SPECS.map((spec) => spec.path);
    expect(new Set(paths).size).toBe(paths.length);
  });

  it('gives every route a title and an absolute path', () => {
    for (const spec of ALL_ROUTE_SPECS) {
      expect(spec.title.trim(), spec.path).not.toBe('');
      expect(spec.path.startsWith('/'), spec.path).toBe(true);
    }
  });

  it('keeps unauthenticated pages out of the app shell', () => {
    const publicPaths = ALL_ROUTE_SPECS.filter((s) => s.layout !== 'app').map((s) => s.path);
    expect(publicPaths.sort()).toEqual(
      ['/auth/action', '/forgot-password', '/login', '/q/:token', '/signup'].sort(),
    );
  });

  it('maps each pilot screenshot to exactly one route', () => {
    const shots = ALL_ROUTE_SPECS.flatMap((spec) => spec.screenshots ?? []);
    expect(new Set(shots).size).toBe(shots.length);
    expect(shots).toHaveLength(18);
  });

  it('substitutes sample params', () => {
    expect(samplePath('/clients/:id/kpis')).toBe(
      '/clients/00000000-0000-0000-0000-000000000001/kpis',
    );
    expect(samplePath('/q/:token')).toBe('/q/sample-token');
  });
});
