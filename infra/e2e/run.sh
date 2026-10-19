#!/usr/bin/env bash
# Run the Playwright suite against an ISOLATED, throw-away copy of the stack.
#
# A separate Compose project ("delphin-e2e") gets its own database volume,
# Firebase emulator and app containers, so tests never touch the dev data you
# work with on :5173. It is created fresh before the run and deleted after it.
#
# Usage (from the repo root, in Git Bash / WSL / Linux / macOS):
#   infra/e2e/run.sh                 # Playwright on this machine (needs Node + pnpm)
#   E2E_RUNNER=container infra/e2e/run.sh   # Playwright in Docker (what CI uses)
#   E2E_KEEP=1 infra/e2e/run.sh      # keep the e2e stack afterwards for debugging
#   infra/e2e/run.sh -g "clients"    # extra args go to `playwright test`
set -euo pipefail

cd "$(dirname "$0")/../.."

PROJECT="${E2E_PROJECT:-delphin-e2e}"
PORT="${E2E_PORT:-5174}"
DB_PORT="${E2E_DB_PORT:-5433}"
RUNNER="${E2E_RUNNER:-host}"
E2E_EMAIL="${E2E_EMAIL:-e2e@example.com}"
E2E_PASSWORD="${E2E_PASSWORD:-e2e-password-not-secret}"
export E2E_EMAIL E2E_PASSWORD

# Same files as `docker compose up` (base + dev override), different project and ports.
compose() {
  FRONTEND_PORT="$PORT" POSTGRES_PORT="$DB_PORT" \
    docker compose -p "$PROJECT" -f compose.yaml -f compose.override.yaml "$@"
}

cleanup() {
  if [[ "${E2E_KEEP:-0}" == "1" ]]; then
    echo "e2e: keeping stack '$PROJECT' on http://localhost:$PORT (remove: docker compose -p $PROJECT down -v)"
  else
    echo "e2e: removing stack '$PROJECT' and its data"
    compose --profile e2e down -v --remove-orphans >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

echo "e2e: starting a fresh isolated stack '$PROJECT' on http://localhost:$PORT"
compose --profile e2e down -v --remove-orphans >/dev/null 2>&1 || true
# --build: dependency changes (package.json / uv.lock) must reach the throw-away images.
compose up -d --build --wait db migrate firebase backend frontend

echo "e2e: warming up the dev server (compiling every page once)"
# A brand-new Vite server compiles each module on first request; doing that here
# keeps cold-start compile time out of the tests' own timeouts.
for module in src/main.tsx $(cd frontend && find src/features src/components src/app -name '*.tsx' | sort); do
  curl -s -o /dev/null --max-time 120 "http://localhost:$PORT/$module" || true
done

echo "e2e: creating test accounts"
compose run --rm -T backend python scripts/seed_config.py
compose run --rm -T backend python scripts/dev_create_user.py \
  "$E2E_EMAIL" "E2E Admin" super_admin "$E2E_PASSWORD"
compose run --rm -T backend python scripts/dev_create_user.py \
  e2e-flows@example.com "E2E Flows" employee 'flows-password-original' --unverified

if [[ "$RUNNER" == "container" ]]; then
  echo "e2e: running Playwright in Docker"
  compose --profile e2e run --rm e2e sh -c \
    "npm i -g pnpm@10.17.0 >/dev/null && pnpm install --frozen-lockfile && pnpm exec playwright test $*"
else
  echo "e2e: running Playwright on this machine"
  (cd frontend && E2E_BASE_URL="http://localhost:$PORT" pnpm exec playwright test --workers=4 "$@")
fi
