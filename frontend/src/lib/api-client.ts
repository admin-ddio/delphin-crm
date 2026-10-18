import createClient, { type Middleware } from 'openapi-fetch';

import type { components, paths } from '@/api/schema';

/** The backend's ErrorEnvelope body (generated type; `details`/`request_id` normalised). */
export type ApiErrorBody = Required<components['schemas']['ErrorBody']>;

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown>;
  readonly requestId: string | null;

  constructor(status: number, body: ApiErrorBody) {
    super(body.message);
    this.name = 'ApiError';
    this.status = status;
    this.code = body.code;
    this.details = body.details;
    this.requestId = body.request_id;
  }
}

export const CSRF_COOKIE = 'delphin_csrf';
export const CSRF_HEADER = 'X-CSRF-Token';
const UNSAFE_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

export function readCookie(name: string): string | undefined {
  return document.cookie
    .split('; ')
    .find((row) => row.startsWith(`${name}=`))
    ?.slice(name.length + 1);
}

const csrfMiddleware: Middleware = {
  onRequest({ request }) {
    if (UNSAFE_METHODS.has(request.method)) {
      const token = readCookie(CSRF_COOKIE);
      if (token) request.headers.set(CSRF_HEADER, decodeURIComponent(token));
    }
    return request;
  },
};

/** Same-origin client: Vite proxies /api in dev, nginx in production. */
export const api = createClient<paths>({ baseUrl: '', credentials: 'same-origin' });
api.use(csrfMiddleware);

/** Unwrap an openapi-fetch result or throw ApiError (for use inside TanStack Query fns). */
export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.error !== undefined || result.data === undefined) {
    const envelope = result.error as { error?: ApiErrorBody } | undefined;
    throw new ApiError(
      result.response.status,
      envelope?.error ?? {
        code: 'unknown_error',
        message: result.response.statusText || 'Request failed',
        details: {},
        request_id: result.response.headers.get('X-Request-ID'),
      },
    );
  }
  return result.data;
}
