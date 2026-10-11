# Local development

Run all of Popshot on your machine. Nothing here touches Google Cloud.

| Piece | Where it runs | Address |
|---|---|---|
| Web app (`next dev`, live reload) | your machine | http://127.0.0.1:3000 |
| API (`uvicorn --reload`) | your machine | http://127.0.0.1:8000 (docs at `/docs`) |
| Postgres 16 | container | 127.0.0.1:54329 |
| Firebase Auth emulator | container | 127.0.0.1:9099 |

## Before the first run

- OrbStack, Colima or Docker Desktop, running
- [uv](https://docs.astral.sh/uv/) (`brew install uv`)
- Node 24: `brew install node@24`. Your default `node` can stay on a newer version; `run.sh` finds Homebrew's node@24 by itself.

## Commands

```sh
./dev/run.sh          # start everything; Ctrl-C stops the API and web app
./dev/run.sh test     # API checks and tests (with the database) and web checks and unit tests
./dev/run.sh stop     # stop the containers; your local data is kept
./dev/run.sh reset    # delete the local database (asks first)
```

The first run builds the emulator image and installs dependencies, so it takes a few minutes.
After that it starts in seconds.

## Signing in

Click **Sign in with Google**. The emulator opens its own popup instead of Google's: choose
**Add new account**, type any email (for example `alice@example.com`) and sign in. To act as a
second person, use a private window and another email, such as `bob@example.com`.

These accounts exist only inside the emulator and disappear when it restarts. The rows
Popshot created for them stay in the local database.

## How it stays local-only

The emulator signs nothing, so its tokens could be made by anyone. They're accepted only
when all of these hold (the web app and the API each refuse to start otherwise):

- the Firebase project is `demo-popshot`, a `demo-*` project, which Firebase keeps offline;
- the API runs with `POPSHOT_ENVIRONMENT=local` and `POPSHOT_AUTH_EMULATOR=true`;
- the emulator address is on loopback (`127.0.0.1` or `localhost`);
- it isn't Cloud Run (`K_SERVICE` unset).

Production sets `POPSHOT_ENVIRONMENT=prod` and a real project, so it can't be switched on
there by accident.

## Database

Same role layout as CI and Cloud SQL (ADR 0004, ADR 0005): `popshot_migrator` runs migrations
and `popshot_api` is what the API logs in as, under row-level security. `run.sh` creates the
roles, runs the bootstrap and `alembic upgrade head` on every start, so new migrations apply
automatically.

The passwords are random, made on the first run and kept in `.dev/secrets.env` (gitignored,
readable only by you). To look around with psql:

```sh
. .dev/secrets.env
psql "postgresql://popshot_api:${POPSHOT_DEV_API_PASSWORD}@127.0.0.1:54329/popshot"
```

## The emulator image

`auth-emulator/` builds `firebase-tools` (version pinned in its Dockerfile) on the same Node
base image as the web app. Its dependencies are resolved when the image is built, limited to
versions published before a fixed date. Some of them have known advisories (in proxy, FTP and
file-watching code the Auth emulator doesn't use). That's accepted because the container only
listens on your own machine, runs as a non-root user on a read-only filesystem with no
capabilities, and is never built in CI or deployed. To move to a newer `firebase-tools`, change
both `FIREBASE_TOOLS_VERSION` and `NPM_BEFORE`.
