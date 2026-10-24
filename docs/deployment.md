# Deployment

The production profile is `compose.yaml` + `compose.prod.yaml`:

- `edge`: nginx (non-root, read-only) serves the built SPA and proxies `/api` to `backend`. It is the
  only published port (8080).
- `backend`: gunicorn with uvicorn workers, read-only filesystem, non-root.
- `migrate`: runs `alembic upgrade head` once before `backend` starts.
- `db`: PostgreSQL 16 with a named volume. In real production, prefer a managed Postgres 16 and point
  `DATABASE_URL` at it.

## Steps

```bash
cp .env.example .env
# Set: APP_ENV=production, strong POSTGRES_PASSWORD, SECRET_KEY and CRON_SECRET (openssl rand -hex 32),
#      ALLOWED_HOSTS=<public host>, APP_BASE_URL=https://<public host>, CORS_ORIGINS empty.
make prod-up            # builds and waits until healthy; serves http://localhost:8080
```

The backend refuses to start in production with placeholder or short secrets, wildcard hosts or CORS
origins.

## TLS

Terminate TLS in front of `edge` (load balancer, ingress or a host reverse proxy) and forward
`X-Forwarded-Proto`. HSTS is sent by both the edge and the API in production.

## Scheduled jobs

Call `POST /api/v1/jobs/run` with `Authorization: Bearer $CRON_SECRET` from an external scheduler
(currently a 501 stub), or run `python scripts/run_jobs.py` in the backend image.

## First administrator

Either way needs real Firebase configured (see "Firebase Auth" below).

**Sign in straight away** with an e-mail and a password you choose. The script seeds the roles,
creates or updates the Firebase account with a verified e-mail, and grants `super_admin`. It prompts
for the password (12+ characters in production) or reads `SUPER_ADMIN_PASSWORD`. Re-run it to reset
the password or to repair an account first created in the emulator.

```bash
docker compose -f compose.yaml -f compose.prod.yaml run --rm \
  -v /path/to/service-account.json:/run/secrets/firebase.json:ro \
  -e GOOGLE_APPLICATION_CREDENTIALS=/run/secrets/firebase.json \
  backend python scripts/seed_super_admin.py <email> "<name>"
```

**Or invite** with a one-time password-setup link: seed roles with `make seed-config`, then
`docker compose run --rm backend python scripts/create_super_admin.py <email> "<name>"`.

## Migrations and rollback

Migrations run automatically on deploy. Downgrading past `0001` drops the audit log and is refused when
`APP_ENV=production`, unless `ALLOW_AUDIT_LOG_DOWNGRADE=true` is set explicitly.

## Firebase Auth (sign-in, e-mail verification, password reset)

See ADR-0009. Development uses the local emulator automatically. For a real project:

1. Firebase console → create (or pick) a project → **Authentication → Sign-in method** → enable
   **Email/Password**.
2. **Project settings → Your apps → Web app**: copy the config into `.env`:
   `VITE_FIREBASE_API_KEY`, `VITE_FIREBASE_AUTH_DOMAIN`, `VITE_FIREBASE_APP_ID`, and
   `FIREBASE_PROJECT_ID` (also used as the web `projectId`).
3. Set `VITE_FIREBASE_USE_EMULATOR=false` and leave `FIREBASE_AUTH_EMULATOR_HOST` empty.
4. **Project settings → Service accounts → Generate new private key**. Mount the JSON into the backend
   container as a secret and set `GOOGLE_APPLICATION_CREDENTIALS` to its path. It's needed to create
   users (invitations); never commit it.
5. **Authentication → Settings → Authorized domains**: add your app's domain.
6. Optional: **Authentication → Templates → Customize action URL** →
   `https://<your-domain>/auth/action`, so verification and reset links open inside the app.
   Customise the e-mail templates and sender name there too.
7. First administrator:
   `docker compose run --rm backend python scripts/create_super_admin.py <email> "<name>"` prints a
   one-time password-setup link.
