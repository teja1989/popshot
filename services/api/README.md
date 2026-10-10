# Popshot API

FastAPI service that owns Popshot's data, rules and stats. It runs privately on Cloud Run and
only the web app's service account can call it. See [docs/architecture.md](../../docs/architecture.md).

## Setup

Needs Python 3.13 and [uv](https://docs.astral.sh/uv/) 0.11.32 or later.

```sh
cd services/api
uv sync --all-groups
```

## Database

The API needs Postgres 16 and two roles. Create them once (as a superuser) with random
passwords:

```sh
psql -v ON_ERROR_STOP=1 -v owner_password="$(openssl rand -hex 24)" \
     -v app_password="$(openssl rand -hex 24)" -f db/init_roles.sql "$ADMIN_URL"
```

Then run migrations as the owner, and point the API and tests at the app role:

```sh
export POPSHOT_MIGRATION_DATABASE_URL=postgresql+psycopg://popshot_owner:...@localhost/popshot
export POPSHOT_TEST_APP_DATABASE_URL=postgresql+psycopg://popshot_app:...@localhost/popshot
uv run alembic upgrade head
```

Isolation rules are in [ADR 0002](../../docs/adr/0002-tenant-isolation-rls.md) and
[ADR 0004](../../docs/adr/0004-rls-implementation.md). The isolation tests in `tests/db/` run
when both URLs are set; otherwise they're skipped. CI sets `POPSHOT_REQUIRE_DB=1`, which
turns a missing database into a failure.

A new table holding group data needs: `group_id`, composite foreign keys to its parents,
`ENABLE` and `FORCE ROW LEVEL SECURITY`, policies for `popshot_app`, grants that never include
UPDATE on `group_id`, and an entry in `TABLES` in `tests/db/test_isolation.py`. A catalog test
fails if any table is missing from that list or lacks forced RLS.

## Checks

The same checks CI runs:

```sh
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run alembic upgrade head && uv run alembic downgrade base && uv run alembic upgrade head
uv run pytest
uv export --no-emit-project --all-groups --format requirements-txt > /tmp/req.txt
uv run pip-audit --strict --disable-pip -r /tmp/req.txt
```

Set `HYPOTHESIS_PROFILE=ci` to run the property tests with more examples.

## Running locally

```sh
POPSHOT_FIREBASE_PROJECT_ID=<your-dev-project-id> \
POPSHOT_DATABASE_URL=postgresql+psycopg://popshot_app:...@localhost/popshot \
  uv run uvicorn --factory popshot_api.main:create_app --reload
```

The API refuses to start unless it's connected as `popshot_app` with no extra privileges.

`/docs` is only served when `POPSHOT_ENVIRONMENT` is `local` (the default).

## Configuration

All settings come from environment variables. Nothing is read from `.env` files.

| Variable | Required | Default | Meaning |
|---|---|---|---|
| `POPSHOT_FIREBASE_PROJECT_ID` | yes | | Project that issues users' ID tokens (token audience) |
| `POPSHOT_DATABASE_URL` | yes | | SQLAlchemy URL for the `popshot_app` role |
| `POPSHOT_ENVIRONMENT` | no | `local` | `local`, `test`, `dev` or `prod` |
| `POPSHOT_ALLOWED_SIGN_IN_PROVIDERS` | no | `["google.com"]` | JSON list of accepted sign-in providers |
| `POPSHOT_LOG_LEVEL` | no | `INFO` | `DEBUG`, `INFO`, `WARNING` or `ERROR` |

## Authentication

Every request except `/healthz` needs `Authorization: Bearer <Identity Platform ID token>`.
The API checks the signature against Google's published keys, then issuer, audience, expiry,
issued-at, auth time, subject, sign-in provider and `email_verified`. It never trusts identity
claims from the web layer.

On Cloud Run the web service proves who it is with the `X-Serverless-Authorization` header, so
`Authorization` stays free for the user's token.

Tests use `tests/fakes.py:FakeTokenVerifier`, which lives under `tests/` so it can't ship.

## Logging

One JSON object per line on stdout, with a `severity` field for Cloud Logging. Request logs
include method, path, status, duration, a request ID and the Cloud Trace ID. Query strings,
headers and bodies are never logged.

## Container image

```sh
docker build -t popshot-api services/api
```

- Python 3.13 slim base, pinned by digest. `uv` comes from its GitHub release, checked by SHA-256 at build time.
- Only runtime dependencies, from the frozen lockfile. No tests, no dev tools, no `pip`.
- Runs as uid 10001 on port 8080 and works with a read-only root filesystem.
- Ships `alembic.ini` and `migrations/`, so the same image runs `alembic upgrade head` as the migration job.

CI builds it on every PR and scans it with Trivy for fixable HIGH/CRITICAL vulnerabilities and baked-in secrets.
