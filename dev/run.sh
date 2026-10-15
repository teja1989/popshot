#!/usr/bin/env bash
# Runs Popshot on your machine. Postgres and the Firebase Auth emulator run in containers
# (Docker, OrbStack or Colima); the API and the web app run directly, with live reload.
#
#   ./dev/run.sh          start everything; Ctrl-C stops the API and web app
#   ./dev/run.sh test     run the API tests (including the database isolation tests) and web unit tests
#   ./dev/run.sh e2e      browser tests against the whole stack (production web build, API,
#                         Postgres, Auth emulator); extra arguments go to Playwright
#   ./dev/run.sh stop     stop the containers (data is kept)
#   ./dev/run.sh reset    stop the containers and delete the local database
#
# Nothing here touches Google Cloud. See dev/README.md.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STATE="$ROOT/.dev"
COMPOSE=(docker compose -f "$ROOT/dev/compose.yaml")

PG_PORT=54329
API_PORT=8000
ADMIN_API_PORT=8001
WEB_PORT=3000
# The full-stack browser tests use their own ports, so they can run next to `up`.
E2E_API_PORT=8100
E2E_ADMIN_API_PORT=8101
E2E_WEB_PORT=3200
EMULATOR_HOST="127.0.0.1:9099"
PROJECT_ID="demo-popshot"
# Who can open /admin locally. Sign in as this address in the emulator (the e2e tests do).
ADMIN_EMAIL="admin@popshot.test"

say() { printf '==> %s\n' "$*"; }
die() { printf 'x %s\n' "$*" >&2; exit 1; }

check_tools() {
  command -v docker >/dev/null || die "Docker isn't installed. Install OrbStack (brew install orbstack) or Colima."
  docker info >/dev/null 2>&1 || die "Docker isn't running. Start OrbStack or 'colima start', then re-run."
  docker compose version >/dev/null 2>&1 || die "'docker compose' is missing (brew install docker-compose)."
  command -v uv >/dev/null || die "uv isn't installed (brew install uv)."
  use_node_24
  for port in "$API_PORT" "$ADMIN_API_PORT" "$WEB_PORT"; do
    if (exec 3<>"/dev/tcp/127.0.0.1/$port") 2>/dev/null; then
      die "Port $port is already in use. Stop whatever is using it, then re-run."
    fi
  done
}

node_major() { node -p 'process.versions.node.split(".")[0]' 2>/dev/null || echo none; }

# Production runs Node 24. If your default node is another version, use Homebrew's node@24
# for this script only (it's keg-only, so your default node stays as it is).
use_node_24() {
  if [ "$(node_major)" != "24" ] && command -v brew >/dev/null; then
    local prefix
    prefix="$(brew --prefix node@24 2>/dev/null || true)"
    if [ -n "$prefix" ] && [ -x "$prefix/bin/node" ]; then
      PATH="$prefix/bin:$PATH"
      export PATH
    fi
  fi
  local major
  major="$(node_major)"
  if [ "$major" != "24" ]; then
    die "Node 24 is needed (found: $(node --version 2>/dev/null || echo none)). Run: brew install node@24
  Your default node stays as it is; this script finds node@24 by itself. (nvm/fnm users: see .nvmrc.)"
  fi
}

# Throwaway passwords for the local database, made once and kept in .dev/ (gitignored).
load_secrets() {
  mkdir -p "$STATE"
  chmod 700 "$STATE"
  if [ ! -f "$STATE/secrets.env" ]; then
    (
      umask 077
      {
        echo "POPSHOT_DEV_SUPERUSER_PASSWORD=$(openssl rand -hex 24)"
        echo "POPSHOT_DEV_MIGRATOR_PASSWORD=$(openssl rand -hex 24)"
        echo "POPSHOT_DEV_API_PASSWORD=$(openssl rand -hex 24)"
      } > "$STATE/secrets.env"
    )
  fi
  # Added with the admin service; older .dev/ folders get it here.
  if ! grep -q '^POPSHOT_DEV_ADMIN_PASSWORD=' "$STATE/secrets.env"; then
    (umask 077 && echo "POPSHOT_DEV_ADMIN_PASSWORD=$(openssl rand -hex 24)" >> "$STATE/secrets.env")
  fi
  # A local Web Push signing key, so notifications can be turned on in development.
  if [ ! -f "$STATE/push-vapid.pem" ]; then
    (umask 077 && openssl ecparam -name prime256v1 -genkey -noout -out "$STATE/push-vapid.pem")
  fi
  PUSH_KEY="$(cat "$STATE/push-vapid.pem")"
  # shellcheck disable=SC1091
  . "$STATE/secrets.env"
  export POPSHOT_DEV_SUPERUSER_PASSWORD
  ADMIN_URL="postgresql://postgres:${POPSHOT_DEV_SUPERUSER_PASSWORD}@127.0.0.1:${PG_PORT}/postgres"
  MIGRATOR_URL="postgresql+psycopg://popshot_migrator:${POPSHOT_DEV_MIGRATOR_PASSWORD}@127.0.0.1:${PG_PORT}/popshot"
  API_DB_URL="postgresql+psycopg://popshot_api:${POPSHOT_DEV_API_PASSWORD}@127.0.0.1:${PG_PORT}/popshot"
  ADMIN_API_DB_URL="postgresql+psycopg://popshot_admin_api:${POPSHOT_DEV_ADMIN_PASSWORD}@127.0.0.1:${PG_PORT}/popshot"
}

start_containers() {
  say "Starting Postgres and the Auth emulator"
  "${COMPOSE[@]}" up --detach --build --wait --quiet-pull
}

# Same role layout as CI and Cloud SQL (ADR 0004, ADR 0005). Safe to run every time.
prepare_database() {
  say "Preparing the database"
  local exists
  exists="$("${COMPOSE[@]}" exec -T postgres psql -U postgres -tAc \
    "SELECT 1 FROM pg_roles WHERE rolname = 'popshot_api'")"
  if [ "$exists" != "1" ]; then
    "${COMPOSE[@]}" exec -T postgres psql -U postgres -v ON_ERROR_STOP=1 \
      -v migrator_password="$POPSHOT_DEV_MIGRATOR_PASSWORD" \
      -v api_password="$POPSHOT_DEV_API_PASSWORD" \
      -f - < "$ROOT/services/api/db/local_login_users.sql" >/dev/null
  fi
  exists="$("${COMPOSE[@]}" exec -T postgres psql -U postgres -tAc \
    "SELECT 1 FROM pg_roles WHERE rolname = 'popshot_admin_api'")"
  if [ "$exists" != "1" ]; then
    "${COMPOSE[@]}" exec -T postgres psql -U postgres -v ON_ERROR_STOP=1 \
      -v admin_password="$POPSHOT_DEV_ADMIN_PASSWORD" -f - >/dev/null <<'SQL'
CREATE ROLE popshot_admin_api LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOREPLICATION
  PASSWORD :'admin_password';
SQL
  fi
  (
    cd "$ROOT/services/api"
    uv sync --frozen --all-groups --quiet
    POPSHOT_BOOTSTRAP_ADMIN_URL="$ADMIN_URL" \
      uv run --frozen python -m popshot_api.ops.bootstrap_db \
      --migrator popshot_migrator --api popshot_api --admin popshot_admin_api >/dev/null
    POPSHOT_MIGRATION_DATABASE_URL="$MIGRATOR_URL" uv run --frozen alembic upgrade head
  )
}

install_web() {
  local stamp="$ROOT/apps/web/node_modules/.popshot-lock"
  local want
  want="$(cksum < "$ROOT/apps/web/package-lock.json")"
  if [ ! -f "$stamp" ] || [ "$(cat "$stamp")" != "$want" ]; then
    say "Installing web dependencies"
    (cd "$ROOT/apps/web" && npm ci --no-audit --no-fund)
    echo "$want" > "$stamp"
  fi
}

run_app() {
  say "Starting the API on :$API_PORT, the admin service on :$ADMIN_API_PORT and the web app on :$WEB_PORT"
  # Global, not local: the EXIT trap runs after this function has returned.
  PIDS=()
  (
    cd "$ROOT/services/api"
    POPSHOT_ENVIRONMENT=local \
    POPSHOT_FIREBASE_PROJECT_ID="$PROJECT_ID" \
    POPSHOT_AUTH_EMULATOR=true \
    POPSHOT_DATABASE_URL="$API_DB_URL" \
    POPSHOT_PUSH_VAPID_PRIVATE_KEY="$PUSH_KEY" \
    POPSHOT_PLACES=fake \
      exec uv run --frozen uvicorn --factory popshot_api.main:create_app \
      --host 127.0.0.1 --port "$API_PORT" --reload
  ) &
  PIDS+=($!)
  (
    cd "$ROOT/services/api"
    POPSHOT_ENVIRONMENT=local \
    POPSHOT_FIREBASE_PROJECT_ID="$PROJECT_ID" \
    POPSHOT_AUTH_EMULATOR=true \
    POPSHOT_DATABASE_URL="$ADMIN_API_DB_URL" \
    POPSHOT_ADMIN_EMAILS="$ADMIN_EMAIL" \
      exec uv run --frozen uvicorn --factory popshot_api.admin_main:create_admin_app \
      --host 127.0.0.1 --port "$ADMIN_API_PORT" --reload
  ) &
  PIDS+=($!)
  (
    cd "$ROOT/apps/web"
    # Public, made-up values: the emulator accepts any API key for a demo-* project.
    API_BASE_URL="http://127.0.0.1:${API_PORT}" \
    ADMIN_API_BASE_URL="http://127.0.0.1:${ADMIN_API_PORT}" \
    FIREBASE_API_KEY="demo-api-key" \
    FIREBASE_AUTH_DOMAIN="${PROJECT_ID}.firebaseapp.com" \
    FIREBASE_PROJECT_ID="$PROJECT_ID" \
    FIREBASE_APP_ID="1:000000000000:web:0000000000000000" \
    FIREBASE_AUTH_EMULATOR_HOST="$EMULATOR_HOST" \
    NEXT_TELEMETRY_DISABLED=1 \
      exec npm run dev -- --hostname 127.0.0.1 --port "$WEB_PORT"
  ) &
  PIDS+=($!)
  trap 'kill "${PIDS[@]}" 2>/dev/null || true' INT TERM EXIT

  cat <<EOF

  Popshot     http://127.0.0.1:${WEB_PORT}
  API docs    http://127.0.0.1:${API_PORT}/docs
  Sign in with any made-up Google account in the emulator's popup (try alice@example.com,
  then bob@example.com in a private window).

  Ctrl-C stops the app. The containers keep running: ./dev/run.sh stop

EOF
  wait
}

run_tests() {
  say "API: format, lint, types, tests (with the database)"
  (
    cd "$ROOT/services/api"
    uv run --frozen ruff format --check .
    uv run --frozen ruff check .
    uv run --frozen mypy
    POPSHOT_REQUIRE_DB=1 \
    POPSHOT_BOOTSTRAP_ADMIN_URL="$ADMIN_URL" \
    POPSHOT_MIGRATION_DATABASE_URL="$MIGRATOR_URL" \
    POPSHOT_TEST_APP_DATABASE_URL="$API_DB_URL" \
      uv run --frozen pytest -q
  )
  say "Web: lint, types, unit tests"
  (
    cd "$ROOT/apps/web"
    npm run -s lint
    npm run -s typecheck
    npm test
  )
}

wait_for() {
  local url="$1" name="$2" _
  for _ in $(seq 1 90); do
    if curl -fsS -o /dev/null "$url" 2>/dev/null; then
      return 0
    fi
    sleep 1
  done
  die "$name didn't start within 90 seconds (logs in .dev/)."
}

run_e2e() {
  if [ -z "${PLAYWRIGHT_CHROMIUM_EXECUTABLE:-}" ]; then
    local mac_chrome="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if [ -x "$mac_chrome" ]; then
      export PLAYWRIGHT_CHROMIUM_EXECUTABLE="$mac_chrome"
    else
      say "No PLAYWRIGHT_CHROMIUM_EXECUTABLE and no Chrome found; Playwright uses its own browser"
      say "(install it once with: cd apps/web && npx playwright install chromium)"
    fi
  fi

  say "Building the web app (production build)"
  (cd "$ROOT/apps/web" && NEXT_TELEMETRY_DISABLED=1 npm run -s build)

  say "Starting the API on :$E2E_API_PORT, the admin service on :$E2E_ADMIN_API_PORT and the built web app on :$E2E_WEB_PORT"
  PIDS=()
  (
    cd "$ROOT/services/api"
    POPSHOT_ENVIRONMENT=local \
    POPSHOT_FIREBASE_PROJECT_ID="$PROJECT_ID" \
    POPSHOT_AUTH_EMULATOR=true \
    POPSHOT_DATABASE_URL="$API_DB_URL" \
    POPSHOT_PUSH_VAPID_PRIVATE_KEY="$PUSH_KEY" \
    POPSHOT_PLACES=fake \
      exec uv run --frozen uvicorn --factory popshot_api.main:create_app \
      --host 127.0.0.1 --port "$E2E_API_PORT"
  ) > "$STATE/e2e-api.log" 2>&1 &
  PIDS+=($!)
  (
    cd "$ROOT/services/api"
    POPSHOT_ENVIRONMENT=local \
    POPSHOT_FIREBASE_PROJECT_ID="$PROJECT_ID" \
    POPSHOT_AUTH_EMULATOR=true \
    POPSHOT_DATABASE_URL="$ADMIN_API_DB_URL" \
    POPSHOT_ADMIN_EMAILS="$ADMIN_EMAIL" \
      exec uv run --frozen uvicorn --factory popshot_api.admin_main:create_admin_app \
      --host 127.0.0.1 --port "$E2E_ADMIN_API_PORT"
  ) > "$STATE/e2e-admin.log" 2>&1 &
  PIDS+=($!)
  (
    cd "$ROOT/apps/web"
    # Run the standalone server exactly as the container does.
    rm -rf .next/standalone/.next/static
    cp -r .next/static .next/standalone/.next/static
    HOSTNAME=127.0.0.1 \
    PORT="$E2E_WEB_PORT" \
    API_BASE_URL="http://127.0.0.1:${E2E_API_PORT}" \
    ADMIN_API_BASE_URL="http://127.0.0.1:${E2E_ADMIN_API_PORT}" \
    FIREBASE_API_KEY="demo-api-key" \
    FIREBASE_AUTH_DOMAIN="${PROJECT_ID}.firebaseapp.com" \
    FIREBASE_PROJECT_ID="$PROJECT_ID" \
    FIREBASE_APP_ID="1:000000000000:web:0000000000000000" \
    FIREBASE_AUTH_EMULATOR_HOST="$EMULATOR_HOST" \
      exec node .next/standalone/server.js
  ) > "$STATE/e2e-web.log" 2>&1 &
  PIDS+=($!)
  trap 'kill "${PIDS[@]}" 2>/dev/null || true' INT TERM EXIT
  wait_for "http://127.0.0.1:${E2E_API_PORT}/healthz" "The API"
  wait_for "http://127.0.0.1:${E2E_ADMIN_API_PORT}/healthz" "The admin service"
  wait_for "http://127.0.0.1:${E2E_WEB_PORT}/icons/192" "The web app"

  say "Running the full-stack browser tests"
  if ! (
    cd "$ROOT/apps/web"
    POPSHOT_E2E_WEB_URL="http://127.0.0.1:${E2E_WEB_PORT}" \
    POPSHOT_E2E_EMULATOR_URL="http://${EMULATOR_HOST}" \
      npx playwright test -c playwright.full.config.ts "$@"
  ); then
    say "Last lines of the API log (.dev/e2e-api.log):"
    tail -n 30 "$STATE/e2e-api.log" || true
    say "Last lines of the admin service log (.dev/e2e-admin.log):"
    tail -n 30 "$STATE/e2e-admin.log" || true
    say "Last lines of the web log (.dev/e2e-web.log):"
    tail -n 30 "$STATE/e2e-web.log" || true
    die "Full-stack browser tests failed."
  fi
}

case "${1:-up}" in
  up)
    check_tools
    load_secrets
    start_containers
    prepare_database
    install_web
    run_app
    ;;
  test)
    use_node_24
    load_secrets
    start_containers
    prepare_database
    install_web
    run_tests
    ;;
  e2e)
    shift
    use_node_24
    load_secrets
    start_containers
    prepare_database
    install_web
    run_e2e "$@"
    ;;
  stop)
    load_secrets
    "${COMPOSE[@]}" stop
    ;;
  reset)
    load_secrets
    printf 'This deletes the local database (only on this machine). Continue? [y/N] '
    read -r answer
    case "$answer" in
      y|Y|yes) "${COMPOSE[@]}" down --volumes ;;
      *) die "Stopped. Nothing deleted." ;;
    esac
    ;;
  *)
    die "Unknown command '$1'. Use: up (default), test, e2e, stop or reset."
    ;;
esac
