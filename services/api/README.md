# Popshot API

FastAPI service that owns Popshot's data, rules and stats. It runs privately on Cloud Run and
only the web app's service account can call it. See [docs/architecture.md](../../docs/architecture.md).

## Setup

Needs Python 3.13 and [uv](https://docs.astral.sh/uv/) 0.11.32 or later.

```sh
cd services/api
uv sync --all-groups
```

## Checks

The same checks CI runs:

```sh
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest
uv export --no-emit-project --all-groups --format requirements-txt > /tmp/req.txt
uv run pip-audit --strict --disable-pip -r /tmp/req.txt
```

Set `HYPOTHESIS_PROFILE=ci` to run the property tests with more examples.

## Running locally

```sh
POPSHOT_FIREBASE_PROJECT_ID=<your-dev-project-id> \
  uv run uvicorn --factory popshot_api.main:create_app --reload
```

`/docs` is only served when `POPSHOT_ENVIRONMENT` is `local` (the default).

## Configuration

All settings come from environment variables. Nothing is read from `.env` files.

| Variable | Required | Default | Meaning |
|---|---|---|---|
| `POPSHOT_FIREBASE_PROJECT_ID` | yes | | Project that issues users' ID tokens (token audience) |
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
