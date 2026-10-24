# Production setup

A step-by-step guide to setting up a Linux server from nothing to a working sign-in, then the tasks
that finish the setup. [deployment.md](deployment.md) describes the production stack. This page is the
checklist for building it.

Run every command from the project folder on the server. **Always pass both compose files.** Plain
`docker compose` also loads `compose.override.yaml`, the development setup (Firebase emulator, Vite dev
server, published DB port).

```bash
# used throughout this page
alias dc='docker compose -f compose.yaml -f compose.prod.yaml'
```

## 1. Server prerequisites

You need Docker Engine and the **Compose v2+ plugin** (`docker compose`, with a space). The old
`docker-compose` v1.29 binary rejects `compose.yaml` with `'name' does not match any of the regexes`.

```bash
docker compose version        # needs v2 or newer
```

If it prints `unknown command: docker compose`, add the plugin. Neither method below touches Docker
Engine, so other containers on the server keep running.

```bash
# Ubuntu (docker.io from the Ubuntu archive)
sudo apt-get install -y docker-compose-v2

# Any distribution, no sudo (current user only)
mkdir -p ~/.docker/cli-plugins
curl -fsSL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-$(uname -m)" \
  -o ~/.docker/cli-plugins/docker-compose
chmod +x ~/.docker/cli-plugins/docker-compose
```

The `edge` container publishes port **8080** (`EDGE_PORT`). If another project already uses it, choose
a free port.

## 2. Get the code

```bash
git clone https://github.com/admin-ddio/delphin-crm.git
cd delphin-crm
git checkout main
```

## 3. Firebase project

Firebase is the only sign-in method ([ADR-0009](adr/0009-firebase-auth-identity-provider.md)). It holds
the passwords; the app holds users, roles and sessions.

In the [Firebase console](https://console.firebase.google.com/):

1. Create or pick a project. Under **Authentication → Sign-in method**, enable **Email/Password**.
2. **Project settings → Your apps → Web app**: note `apiKey`, `authDomain`, `projectId` and `appId`.
   You need them for `.env` in step 5.
3. **Authentication → Settings → Authorized domains**: add the domain users open the app on.
4. **Project settings → Service accounts → Generate new private key** downloads a JSON key. It's a full
   admin credential for the project: never commit it, e-mail it or paste it in chat.

## 4. Service-account key

The backend uses the key for **every** Firebase call, sign-in included. `compose.prod.yaml` mounts
`secrets/firebase-service-account.json` into the backend as `/run/secrets/firebase.json` and points
`GOOGLE_APPLICATION_CREDENTIALS` at it. The `secrets/` folder is git-ignored.

```bash
mkdir -p secrets
mv ~/<project>-firebase-adminsdk-*.json secrets/firebase-service-account.json
chmod 700 secrets                                   # other users can't open the folder
chmod 444 secrets/firebase-service-account.json     # the container (uid 10001) can read the file
git check-ignore -v secrets/firebase-service-account.json   # must print a .gitignore rule
```

The file must exist **before** the first `up`. If it's missing, older Compose releases create an empty
*folder* at that path. Delete that folder and put the file there.

To keep the key elsewhere, set `FIREBASE_CREDENTIALS_FILE=/path/to/key.json` in `.env`.

## 5. Environment file

```bash
cp .env.example .env
sed -i "s/^SECRET_KEY=.*/SECRET_KEY=$(openssl rand -hex 32)/" .env
sed -i "s/^CRON_SECRET=.*/CRON_SECRET=$(openssl rand -hex 32)/" .env
sed -i "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$(openssl rand -hex 24)/" .env
```

Then edit `.env` and set:

| Variable | Production value | Why |
|---|---|---|
| `APP_ENV` | `production` | Enables the production checks, HSTS and redacted errors, and hides `/api/docs` |
| `APP_BASE_URL` | `https://crm.example.com` | Used in e-mailed links. `localhost` here produces broken links |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1,backend,crm.example.com` | Host names the API accepts. Without your domain: `Invalid host header`. Keep `localhost` for the health check |
| `CORS_ORIGINS` | *(empty)* | The SPA is served from the same origin. Refused in production |
| `FIREBASE_PROJECT_ID` | your project ID | Not `demo-delphin` |
| `FIREBASE_AUTH_EMULATOR_HOST` | *(empty)* | When set, users are created in the emulator and token signatures aren't checked. Refused in production |
| `VITE_FIREBASE_API_KEY` | web `apiKey` | Compiled into the SPA at build time |
| `VITE_FIREBASE_AUTH_DOMAIN` | web `authDomain` | " |
| `VITE_FIREBASE_APP_ID` | web `appId` | " |
| `VITE_FIREBASE_USE_EMULATOR` | `false` | `compose.prod.yaml` forces this off as well |
| `EDGE_PORT` | `8080` or a free port | Published port of the `edge` container |

Rules the backend enforces at startup when `APP_ENV=production`:

- `SECRET_KEY` and `CRON_SECRET`: at least 32 characters, and must not contain `change-me`. These are
  random keys, not passwords. Generate them as shown above.
- **No `$` in any value.** Compose treats `$name` in `.env` as a variable and silently drops it, which
  shortens the secret.
- Set `POSTGRES_PASSWORD` **before** the first start. Postgres applies it only when the volume is
  created (see [Troubleshooting](#troubleshooting)).

## 6. Start the stack

```bash
dc up -d --build --wait
dc ps            # db, backend and edge healthy; migrate exited 0
```

`migrate` applies the database migrations and exits before `backend` starts.

## 7. First Super Admin

```bash
dc run --rm backend python scripts/seed_super_admin.py admin@example.com "Full Name"
```

The script prompts for the password twice (12+ characters), seeds the roles, creates or updates the
Firebase account with a verified e-mail, and grants `super_admin`. The last line **must** say
`(Firebase project <your-id>)`. If it says `(the Firebase Auth Emulator)`, `.env` still has
`FIREBASE_AUTH_EMULATOR_HOST` set.

Re-run the same command at any time to reset the password or unlock the account.

The `interim permission catalogue` warning is expected until the pilot's permissions are ported (see
[Finish the setup](#finish-the-setup)).

## 8. Verify

```bash
dc exec backend sh -c 'echo "APP_ENV=$APP_ENV GAC=$GOOGLE_APPLICATION_CREDENTIALS"; ls -l /run/secrets/'
curl -fsS -H "Host: crm.example.com" http://localhost:8080/healthz-edge && echo edge ok
```

Expected: `APP_ENV=production GAC=/run/secrets/firebase.json`, the key file listed, and `edge ok`. Then
sign in at `APP_BASE_URL` with the Super Admin's e-mail and password.

## Updating

```bash
git pull origin main
dc up -d --build --wait
```

The images contain the code: a `git pull` alone changes nothing until you rebuild. After editing `.env`
or the compose files, `up -d` recreates the affected containers. `restart` doesn't pick up changes.

## Finish the setup

The stack runs. These tasks remain before real use:

- [ ] **HTTPS.** Terminate TLS in front of `edge` (host nginx/Caddy, a load balancer or an ingress) and
      forward `Host` and `X-Forwarded-Proto`. Then set `APP_BASE_URL=https://…` and rebuild.
- [ ] **Firebase action URL.** **Authentication → Templates → Customize action URL** →
      `https://<your-domain>/auth/action`, so verification and reset links open inside the app. Set the
      sender name and e-mail templates there too.
- [ ] **Database backups.** The data lives in the `delphin-crm_pgdata` volume. Schedule a dump and keep
      copies off the server:
      ```bash
      dc exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB"' > "backup-$(date +%F).dump"
      ```
      Test a restore once, e.g. into a scratch database with `pg_restore`.
- [ ] **Scheduled jobs.** Call `POST /api/v1/jobs/run` with `Authorization: Bearer $CRON_SECRET` from
      cron (currently a stub that returns 501).
- [ ] **Permission catalogue.** Replace the interim catalogue with the pilot's `permissions.ts`
      (`app/authz/permissions.py`), then re-run `scripts/seed_config.py`.
- [ ] **Add the team.** There's no invite screen yet. Each person uses **Sign up** on the sign-in page,
      verifies their e-mail, then waits. The Super Admin approves them and picks a role on the **Team**
      page. For another Super Admin, run the step 7 command with their e-mail.
- [ ] **Key hygiene.** Delete any other copies of the service-account key (Downloads, home folder). If a
      copy ever leaks, delete that key under **Service accounts** in the Firebase console and generate a
      new one.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `docker: unknown command: docker compose` | Compose plugin missing | [Step 1](#1-server-prerequisites) |
| `'name' does not match any of the regexes: '^x-'` | Old `docker-compose` v1 | Use `docker compose` (v2) |
| `required variable SECRET_KEY is missing a value` | No `.env` | [Step 5](#5-environment-file) |
| `Invalid host header` on every API call | Domain missing from `ALLOWED_HOSTS` | Add it, then `dc up -d` |
| Backend `Error` / `SECRET_KEY is too weak for production` | Shorter than 32 characters, contains `change-me`, or a `$` was dropped | Regenerate with `openssl rand -hex 32` |
| `FIREBASE_AUTH_EMULATOR_HOST must be empty in production` | Development value left in `.env` | Set it to empty |
| Seed prints `(the Firebase Auth Emulator)`; sign-in says wrong password | User created in the emulator, not real Firebase | Empty `FIREBASE_AUTH_EMULATOR_HOST`, re-run the seed |
| `EMAIL_NOT_FOUND` at sign-in | The user doesn't exist in the real Firebase project | Run the seed (step 7) |
| `DefaultCredentialsError` / 500 on `POST /auth/session` | Backend can't see the key: old `compose.prod.yaml`, or container not recreated | `git pull`, then `dc up -d --force-recreate backend`. Check with step 8 |
| `ls: cannot access '/run/secrets/'` inside the backend | Same: the mount isn't applied | Same |
| `PermissionError: '/run/secrets/firebase.json'` | Key not readable by uid 10001 | `chmod 444 secrets/firebase-service-account.json` |
| `python: can't open file '/app/scripts/…'` | Image built before the script existed | `git pull` and `dc up -d --build` |
| `service "migrate" didn't complete successfully` after changing `POSTGRES_PASSWORD` | Postgres keeps the password from when the volume was created | Keep data: `dc exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'`, then `\password <user>` with the new value. Or start empty: `dc down -v` (**deletes all data**), then `dc up -d --build --wait` and step 7 |
| Links in e-mails point to `localhost` | `APP_BASE_URL` not set | Set it, then `dc up -d` |

Logs for any service: `dc logs <service> --tail=80` (`backend`, `migrate`, `edge`, `db`).
