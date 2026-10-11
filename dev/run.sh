#!/usr/bin/env bash
# Runs Popshot on your machine. Postgres and the Firebase Auth emulator run in containers
# (Docker, OrbStack or Colima); the API and the web app run directly, with live reload.
#
#   ./dev/run.sh          start everything; Ctrl-C stops the API and web app
#   ./dev/run.sh test     run the API tests (including the database isolation tests) and web unit tests
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
WEB_PORT=3000
EMULATOR_HOST="127.0.0.1:9099"
PROJECT_ID="demo-popshot"

say() { printf '==> %s\n' "$*"; }
die() { printf 'x %s\n' "$*" >&2; exit 1; }

check_tools() {
  command -v docker >/dev/null || die "Docker isn't installed. Install OrbStack (brew install orbstack) or Colima."
  docker info >/dev/null 2>&1 || die "Docker isn't running. Start OrbStack or 'colima start', then re-run."
  docker compose version >/dev/null 2>&1 || die "'docker compose' is missing (brew install docker-compose)."
  command -v uv >/dev/null || die "uv isn't installed (brew install uv)."
  command -v node >/dev/null || die "Node 24 isn't installed (brew install node@24)."
  local major
  major="$(node -p 'process.versions.node.split(".")[0]')"
  [ "$major" = "24" ] || die "Node 24 is needed; found $(node --version)."
  for port in "$API_PORT" "$WEB_PORT"; do
    if (exec 3<>"/dev/tcp/127.0.0.1/$port") 2>/dev/null; then
      die "Port $port is already in use. Stop whatever is using it, then re-run."
    fi
  done
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
  # shellcheck disable=SC1091
  . "$STATE/secrets.env"
  export POPSHOT_DEV_SUPERUSER_PASSWORD
  ADMIN_URL="postgresql://postgres:${POPSHOT_DEV_SUPERUSER_PASSWORD}@127.0.0.1:${PG_PORT}/postgres"
  MIGRATOR_URL="postgresql+psycopg://popshot_migrator:${POPSHOT_DEV_MIGRATOR_PASSWORD}@127.0.0.1:${PG_PORT}/popshot"
  API_DB_URL="postgresql+psycopg://popshot_api:${POPSHOT_DEV_API_PASSWORD}@127.0.0.1:${PG_PORT}/popshot"
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
  (
    cd "$ROOT/services/api"
    uv sync --frozen --all-groups --quiet
    POPSHOT_BOOTSTRAP_ADMIN_URL="$ADMIN_URL" \
      uv run --frozen python -m popshot_api.ops.bootstrap_db \
      --migrator popshot_migrator --api popshot_api >/dev/null
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
  say "Starting the API on :$API_PORT and the web app on :$WEB_PORT"
  # Global, not local: the EXIT trap runs after this function has returned.
  PIDS=()
  (
    cd "$ROOT/services/api"
    POPSHOT_ENVIRONMENT=local \
    POPSHOT_FIREBASE_PROJECT_ID="$PROJECT_ID" \
    POPSHOT_AUTH_EMULATOR=true \
    POPSHOT_DATABASE_URL="$API_DB_URL" \
      exec uv run --frozen uvicorn --factory popshot_api.main:create_app \
      --host 127.0.0.1 --port "$API_PORT" --reload
  ) &
  PIDS+=($!)
  (
    cd "$ROOT/apps/web"
    # Public, made-up values: the emulator accepts any API key for a demo-* project.
    API_BASE_URL="http://127.0.0.1:${API_PORT}" \
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
    load_secrets
    start_containers
    prepare_database
    install_web
    run_tests
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
    die "Unknown command '$1'. Use: up (default), test, stop or reset."
    ;;
esac
