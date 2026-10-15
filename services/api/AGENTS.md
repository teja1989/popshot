# API (`services/api`)

FastAPI on Python 3.13 with SQLAlchemy Core (plain SQL through `text()`), Postgres 16 and
Alembic. Setup, checks and configuration are in `README.md`. The repository-wide rules are in
`/AGENTS.md`.

## Shape of a request

- Every signed-in route takes `CurrentUserSession` (`src/popshot_api/db.py`): one transaction,
  with `app.user_id` set for row-level security, committed before the response is sent.
  Public routes use `PublicSession` (read-only, no user) and read only through functions
  made for them.
- Write plain SQL through `text()` with bound parameters, never string formatting.
- Errors are `HTTPException`s whose `detail` is written for people: it's shown in the app.
  Something you can't see is a 404, never a 403, so its existence isn't revealed
  (`NOT_FOUND` in `routes/groups.py`).
- Request logs carry method, route, status and `duration_ms`, and never query strings,
  headers or bodies (`middleware.py`). Don't log tokens, invite codes or what people wrote.

## The database is the security boundary

- Roles: `popshot_owner` owns everything (migrations); `popshot_app` is what the API runs as
  and can't bypass row-level security; `popshot_jobs` is the scheduled job (`ops/tick.py`);
  `popshot_admin` is the admin service. See ADR 0004 and 0005. The API refuses to start
  with a more powerful login.
- Row-level security is enabled and forced on every table. Group data checks membership
  (`app_is_member`, `app_is_admin`, ...). Personal data is owner-only and never stored on
  `users`, which crewmates can read.
- Anything that crosses people or crews (joining, inviting, jobs, admin) is a
  `SECURITY DEFINER` function that checks the caller itself and sets
  `search_path = pg_catalog, pg_temp`. `test_role_safety.py` fails otherwise.
- **Limits** live in the database: count recent rows in a table and raise SQLSTATE `PS429`.
  The route maps it to a 429 (`routes/direct_invites.py`, migration 0018).
- **Admin** is a separate service (`admin_main.py`) with its own login. Every change needs a
  recent sign-in and a reason, and is written to `admin_actions`.
- **Deleting an account** sets `users.deleted_at`. Triggers then wipe that person's private
  rows (for example `app_forget_journey`). New personal data needs the same, and must appear
  in the data download (`routes/export.py`).

## Migrations

Follow the `new-migration` skill. In short:
- one file, `migrations/versions/NNNN_name.py`, with a docstring saying what changes and why
  in plain words;
- a `downgrade()` that works: CI runs upgrade, downgrade to base, then upgrade again;
- tests in `tests/db/`, including the isolation list in `test_isolation.py`, which fails if a
  table is missing from it.

## AI (Gemini on Vertex AI)

- Follow the recap writer (`ai_recap.py`) and the journey writer (`journey_ai.py`):
  - a person's consent where it's personal;
  - a feature switch that falls back to Popshot's own words;
  - checked output (lengths, no links or handles, numbers must come from the facts);
  - the person's text treated as data, never instructions;
  - a hash cache;
  - daily limits.
- Send first names only, and nothing about people not in the facts.

## Tests

`uv run pytest`. Tests marked `db` need Postgres; CI sets `POPSHOT_REQUIRE_DB=1` so they can't
be skipped there. `./dev/run.sh test` runs them all locally. Test what someone else can't do,
not only what you can.
