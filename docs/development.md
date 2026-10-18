# Development

## Setup

```bash
make lock    # first clone only, or after changing dependencies
make up      # http://localhost:5173 ; API docs at /api/docs
```

- `backend/app`, `migrations`, `scripts` and `tests` are bind-mounted; uvicorn reloads on change.
- The whole `frontend/` folder is bind-mounted (except `node_modules`); Vite HMR applies changes.
- File watching uses polling, because Docker Desktop bind mounts on Windows and macOS don't emit
  file-change events.
- Postgres listens on `127.0.0.1:5432` (dev only) with the credentials in `.env`.

## Dev sign-in

Sign-in is not ported yet. **Dev builds** render the shell as a stand-in actor (`lib/dev-actor.ts`).
Switch role with `?__role=finance` (remembered in localStorage). This only changes what the UI shows:
the API still rejects every authenticated request. Production builds have no dev actor.

## Adding dependencies

- Backend: edit `backend/pyproject.toml`, then `make lock && make up`.
- Frontend: edit `frontend/package.json`, then `make lock && make up`.
- **Never upgrade** `tailwindcss` / `@tailwindcss/vite` beyond 4.1.x or `lucide-react` beyond
  0.545.x: they are pinned to the pilot for pixel parity (ADR-0005).

## Porting a feature (the loop)

1. Read the module's `PARITY.md` and the pilot sources it lists.
2. Port the entities to `models.py`, then `make makemigration name=<module>_<change>` and review it.
3. Port the business rules to `service.py`, the queries to `repository.py` (always `apply_scope`),
   and the endpoints to `router.py` with `require_permission(...)`.
4. Port the pilot tests.
5. `make gen-api`, then build the pages in `features/<slot>/` from the pilot JSX (class strings
   verbatim), replacing the placeholder routes.
6. Turn the module's `test.fixme` visual entries into real tests; make them pass.
7. Update the `PARITY.md` and `docs/pilot-parity.md` statuses.

## Useful commands

```bash
docker compose exec backend python -c "from app.authz.permissions import CATALOGUE; print(len(CATALOGUE))"
docker compose exec db psql -U "$POSTGRES_USER" "$POSTGRES_DB"
make seed-config
```
