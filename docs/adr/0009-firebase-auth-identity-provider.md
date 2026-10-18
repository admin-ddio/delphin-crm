# 0009. Firebase Auth as the identity provider; app-owned sessions and authorisation

- Status: accepted (amends ADR-0003)
- Date: 2026-10-16

## Context and problem statement

The product owner asked for Firebase to handle e-mail verification. Firebase only verifies e-mail
addresses of users who sign in through Firebase Auth, so adopting it means moving credentials to
Firebase. The app still needs its own roles, record scopes, audit log and the server-side session
model from ADR-0003, and the pilot's authorisation must be ported unchanged.

## Considered options

1. **Firebase Auth for identity, app for sessions and authorisation**
2. Firebase Auth end to end (Firebase ID tokens on every API call, roles in custom claims)
3. Keep app passwords; mirror users into Firebase only to send its e-mails

## Decision outcome

Option 1.

- **Firebase owns credentials:** passwords, e-mail verification, password-reset e-mails and
  brute-force throttling (the browser uses the Firebase JS SDK, in-memory persistence only).
- **The app owns access:** after a Firebase sign-in the browser sends the ID token once to
  `POST /api/v1/auth/session`. The backend verifies it (Admin SDK), requires
  `email_verified`, requires an invited, active `users` row, links `firebase_uid` on first
  sign-in, then issues the usual opaque HttpOnly session cookie (ADR-0003). Every other request
  uses that cookie, so CSRF, roles, scopes and the audit log are unchanged.
- **Invitations:** `AuthService.invite` creates the Firebase account (no password) and the app user,
  and returns a Firebase password-setup link. First sign-in then requires e-mail verification.
- **E-mail links** land on `/auth/action` (configure Firebase's "Customize action URL") or on
  Firebase's hosted pages. The pilot routes `/reset-password/:token` and `/activate/:token` are
  replaced by these links.
- **Development and CI** use the Firebase Auth Emulator (`demo-delphin`, no Google account), proxied
  through the Vite dev server so the browser and Playwright only ever see the app's origin.

### Consequences

- Good: real verification and reset e-mails without running our own mail delivery for auth.
- Good: authorisation, sessions and audit are untouched; switching identity providers later only
  replaces `platform/identity/firebase.py` and the browser sign-in call.
- Bad: two sources of user data (Firebase account and app row). The app row is authoritative for
  access; `firebase_uid` links them, and a different uid presenting the same e-mail is refused.
- Bad: lockout policy and password rules are now Firebase's, not the pilot's
  (TODO(pilot-port): compare with `services/auth.ts`).
- Ops: production needs the project's web config (`VITE_FIREBASE_*`), `FIREBASE_PROJECT_ID`, and a
  service-account key (`GOOGLE_APPLICATION_CREDENTIALS`) for inviting users; the CSP allows
  `identitytoolkit.googleapis.com` and `securetoken.googleapis.com`.
- `users.password_hash`, `auth_tokens` and the in-memory login rate limiter are no longer used by
  sign-in; remove them in a cleanup migration once the pilot comparison is done.
