# 0003. Server-side database sessions instead of JWT

- Status: accepted
- Date: 2026-10-16

## Context and problem statement

The pilot uses database sessions. The SPA and API share one origin (Vite proxy in dev, nginx in prod).
We need instant revocation (sign-out everywhere, user deactivation) and no token material readable by
JavaScript.

## Considered options

1. Opaque random token in an HttpOnly cookie; SHA-256 of it stored in `sessions`
2. JWT access and refresh tokens

## Decision outcome

Option 1, matching the pilot. Cookies are `HttpOnly`, `SameSite=Lax`, and `Secure` in production.
Cookie-authenticated mutations require a double-submit CSRF token (`X-CSRF-Token` equal to the
`delphin_csrf` cookie).

### Consequences

- Good: revocation is a row update; no key rotation; no tokens in JS.
- Bad: a DB lookup per request (indexed on `token_hash`); acceptable, and cacheable later.
