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

The API needs Postgres 16. The role layout is the same everywhere (ADR 0004, ADR 0005):

| Role | Login | Purpose |
|---|---|---|
| `popshot_owner` | no | Owns every table and function |
| `popshot_app` | no | What RLS policies and grants target |
| `popshot_migrator` (locally) / migrator service account (Cloud SQL) | yes | Member of `popshot_owner`; runs migrations |
| `popshot_api` (locally) / API service account (Cloud SQL) | yes | Member of `popshot_app`; the API connects as this |

Set it up once, locally, as a superuser:

```sh
psql -v ON_ERROR_STOP=1 -v migrator_password="$(openssl rand -hex 24)" \
     -v api_password="$(openssl rand -hex 24)" -f db/local_login_users.sql "$ADMIN_URL"
POPSHOT_BOOTSTRAP_ADMIN_URL="$ADMIN_URL" \
  uv run python -m popshot_api.ops.bootstrap_db --migrator popshot_migrator --api popshot_api
```

The bootstrap is safe to re-run. Then migrate as the migrator and point the tests at the API user:

```sh
export POPSHOT_MIGRATION_DATABASE_URL=postgresql+psycopg://popshot_migrator:...@localhost/popshot
export POPSHOT_TEST_APP_DATABASE_URL=postgresql+psycopg://popshot_api:...@localhost/popshot
export POPSHOT_BOOTSTRAP_ADMIN_URL=postgresql://...   # optional: enables the bootstrap tests
uv run alembic upgrade head
```

On Cloud SQL the login users are IAM users and there are no passwords: set
`POPSHOT_DATABASE_IAM_AUTH=true` and the API and migrations use an access token from the
metadata server as the password.

The isolation tests in `tests/db/` run when both URLs are set; otherwise they're skipped. CI
sets `POPSHOT_REQUIRE_DB=1`, which turns a missing database into a failure. CI also runs the
bootstrap as a non-superuser admin, the way it runs on Cloud SQL.

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
POPSHOT_DATABASE_URL=postgresql+psycopg://popshot_api:...@localhost/popshot \
  uv run uvicorn --factory popshot_api.main:create_app --reload
```

The API refuses to start unless its login user inherits `popshot_app` and nothing more powerful.

`/docs` is only served when `POPSHOT_ENVIRONMENT` is `local` (the default).

## Configuration

All settings come from environment variables. Nothing is read from `.env` files.

| Variable | Required | Default | Meaning |
|---|---|---|---|
| `POPSHOT_FIREBASE_PROJECT_ID` | yes | | Project that issues users' ID tokens (token audience) |
| `POPSHOT_DATABASE_URL` | yes | | SQLAlchemy URL for the API's login user (no password with IAM auth) |
| `POPSHOT_DATABASE_IAM_AUTH` | no | `false` | Log in with an IAM access token from the metadata server (Cloud SQL) |
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
