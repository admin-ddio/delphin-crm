import { describe, expect, it } from 'vitest';

import { ApiError, unwrap } from '@/lib/api-client';
import { toActor } from '@/lib/auth-context';
import { can, canAny, DEFAULT_ROLE_PERMISSIONS, ROLE_KEYS, satisfies } from '@/lib/permissions';
import { createQueryClient } from '@/lib/query-client';
import { cn } from '@/lib/utils';

describe('cn', () => {
  it('merges and dedupes tailwind classes', () => {
    const hidden = false;
    expect(cn('px-2 py-1', hidden && 'hidden', 'px-4')).toBe('py-1 px-4');
  });
});

describe('permissions', () => {
  it('honours the wildcard', () => {
    expect(can(['*'], 'anything.at_all')).toBe(true);
    expect(can(['clients.read'], 'clients.read')).toBe(true);
    expect(can(['clients.read'], 'clients.create')).toBe(false);
    expect(canAny(['clients.read'], ['clients.create', 'clients.read'])).toBe(true);
  });

  it('evaluates rules', () => {
    expect(satisfies([], undefined)).toBe(true);
    expect(satisfies([], 'x.y')).toBe(false);
    expect(satisfies(['x.y'], ['a.b', 'x.y'])).toBe(true);
  });

  it('defines every default role', () => {
    expect(Object.keys(DEFAULT_ROLE_PERMISSIONS).sort()).toEqual([...ROLE_KEYS].sort());
    expect(DEFAULT_ROLE_PERMISSIONS.super_admin).toEqual(['*']);
  });
});

describe('auth', () => {
  it('maps the API user to an actor', () => {
    expect(
      toActor({
        id: 'u1',
        email: 'a@example.com',
        full_name: 'Ada',
        roles: ['finance'],
        permissions: ['finance.view'],
      }),
    ).toEqual({
      id: 'u1',
      email: 'a@example.com',
      fullName: 'Ada',
      roles: ['finance'],
      permissions: ['finance.view'],
    });
  });
});

describe('api client', () => {
  it('unwraps data', () => {
    expect(unwrap({ data: { ok: true }, response: new Response() })).toEqual({ ok: true });
  });

  it('throws ApiError with the envelope', () => {
    const response = new Response(null, { status: 403 });
    try {
      unwrap({
        error: {
          error: { code: 'forbidden', message: 'No', details: {}, request_id: 'r1' },
        },
        response,
      });
      expect.fail('should throw');
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError);
      expect((error as ApiError).status).toBe(403);
      expect((error as ApiError).code).toBe('forbidden');
      expect((error as ApiError).requestId).toBe('r1');
    }
  });

  it('throws a generic ApiError without an envelope', () => {
    expect(() => unwrap({ error: 'boom', response: new Response(null, { status: 502 }) })).toThrow(
      ApiError,
    );
  });
});

describe('query client', () => {
  it('does not retry client errors', () => {
    const retry = createQueryClient().getDefaultOptions().queries?.retry as (
      count: number,
      error: unknown,
    ) => boolean;
    const forbidden = new ApiError(403, { code: 'f', message: '', details: {}, request_id: null });
    const unavailable = new ApiError(503, {
      code: 'u',
      message: '',
      details: {},
      request_id: null,
    });
    expect(retry(0, forbidden)).toBe(false);
    expect(retry(0, unavailable)).toBe(true);
    expect(retry(2, unavailable)).toBe(false);
  });
});
