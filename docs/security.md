# Security

Guarantees inherited from the pilot that must never be weakened:

| Guarantee | Where |
|---|---|
| Redacted errors in production (401/403 lose internal detail; 500s never leak messages or traces) | `core/errors.py` |
| Record-level scopes composed with AND, never dict-merged | `authz/scopes.py`, `tests/unit/test_scopes.py` |
| Append-only audit log (DB trigger rejects UPDATE/DELETE/TRUNCATE) | migration `0001`, `platform/audit` |
| Secret-looking keys redacted before audit/activity writes | `platform/audit/service.py` |
| Login rate limit counts **failed** attempts per account only | `core/security.py` (interface) |
| Restricted documents; files only via an access-checked endpoint | `modules/documents` (slot) |
| Last Super Admin cannot be removed | `modules/settings` (slot) |

## Sessions and cookies

Opaque random token in an HttpOnly cookie; only its SHA-256 is stored (`sessions.token_hash`). Cookies
are `SameSite=Lax`, and `Secure` in production. CSRF uses a double-submit token for cookie-authenticated
mutations (`core/middleware.py: CSRFMiddleware`). See ADR-0003.

## Identity (Firebase Auth, ADR-0009)

Firebase holds passwords and handles e-mail verification, reset e-mails and brute-force throttling.
The backend only accepts a Firebase ID token that verifies for our project **and** has a verified
e-mail, **and** belongs to an invited, active user; it then issues its own session cookie. A
different Firebase uid presenting an already-linked e-mail is refused. The browser keeps Firebase
state in memory only. Invitations print a one-time Firebase password-setup link, never a password.
Service-account keys (`GOOGLE_APPLICATION_CREDENTIALS`) are secrets: mount them, never commit them.

## HTTP hardening

TrustedHost allow-list, body size limit, request IDs, and security headers (CSP, `frame-ancestors 'none'`,
nosniff, Referrer-Policy, COOP, Permissions-Policy, HSTS in production) on the API and at the nginx edge.
CORS is only enabled in development when `CORS_ORIGINS` is set; production refuses to start with it.

## Configuration

All secrets come from `.env` (git-ignored). Production refuses to start with weak or placeholder
secrets. Images run as non-root; the production backend and edge containers are read-only.

## Secret scanning

gitleaks runs in pre-commit and CI (`make secrets-scan`).

## Reporting

Report suspected vulnerabilities privately to the maintainers, not in public issues.
