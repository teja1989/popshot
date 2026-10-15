---
name: new-migration
description: Add or change a Postgres table, column, policy or database function in services/api (an Alembic migration). Use for any schema or data-access change, including new SECURITY DEFINER functions, limits and feature switch rows.
---

# New migration

The database is Popshot's security boundary, so a migration isn't done until tests prove
someone else can't read or change the data. Copy the shape of a recent migration:
`0032_journey.py` for personal data, `0028_events.py` for crew data, `0018_direct_invites.py`
for a limit.

## 1. The file

- `services/api/migrations/versions/NNNN_short_name.py`: the next number, with
  `revision = "NNNN"` and `down_revision` set to the previous number.
- The docstring says, in plain words, what changes, why, who can see and change the data,
  and what happens to it when an account is deleted. Future readers start here.
- SQL goes in module-level strings run by `op.execute`. Name roles by the constants
  (`APP_ROLE = "popshot_app"`, `JOBS_ROLE`, `ADMIN_ROLE`).
- **`downgrade()` undoes everything**, in reverse order. CI runs upgrade, downgrade to base,
  then upgrade again.
- **Backward compatible with the code still running:** migrations run before the new API
  takes traffic. Add first, remove in a later release.

## 2. A new table

- Constraints in the table itself: lengths (`char_length(btrim(x)) BETWEEN 1 AND n`), allowed
  values (`CHECK (x IN (...))`), no links in free text where people can't post links.
- `ALTER TABLE t ENABLE ROW LEVEL SECURITY; ALTER TABLE t FORCE ROW LEVEL SECURITY;` and
  `REVOKE ALL ON t FROM PUBLIC;`.
- Policies for `popshot_app`:
  - **Crew data:** `group_id`, foreign keys that include `group_id` so rows can't point into
    another crew, and policies using `app_is_member(group_id)` / `app_is_admin(group_id)`.
  - **Personal data:** owner-only, `USING (user_id = app_current_user_id())` with the same
    `WITH CHECK`. Never on `users` (crewmates can read it).
- Grant only what the app needs (`GRANT SELECT, INSERT ...`, column lists for `UPDATE`).
  Never `UPDATE` on `group_id`.
- Indexes for the queries the API will run (usually `(group_id, ...)` or `(user_id, ...)`).

## 3. A function that crosses people or crews

`LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp`, schema-qualified
names inside (`public.groups`), checks the caller itself (`app_current_user_id()`, membership,
role, limits), then `REVOKE EXECUTE ... FROM PUBLIC` and `GRANT EXECUTE ... TO` exactly the
role that needs it.

Limits: count recent rows and `RAISE EXCEPTION '...' USING ERRCODE = 'PS429'`. The route
maps it to a 429.

## 4. Personal data also needs

- **Deletion:** a trigger `AFTER UPDATE OF deleted_at ON users` calling an
  `app_forget_*()` function that deletes the rows, plus `owner_definer_read` and
  `owner_definer_delete` policies so it can (see `0032_journey.py`).
- **Export:** include it in the data download (`src/popshot_api/routes/export.py`).
- **Privacy page:** say it's kept (`apps/web/src/app/privacy/page.tsx`).

## 5. Tests (`services/api/tests/db/`)

- **Crew tables:** add a `TableSpec` to `TABLES` in `test_isolation.py`. It checks that
  another crew can't read, insert, update, delete or point at your rows.
- **Personal and function-only tables:** add the name to the `personal` set in
  `test_isolation.py` with a comment naming the test file that covers it, and write those
  tests: another person gets nothing; direct writes are refused.
- **Functions:** the caller checks, the limits (the call past the limit gets `PS429`), and
  what a non-member, a removed member and a deleted account get.
- `test_role_safety.py` runs on its own and catches a function without a pinned
  `search_path` or anything granted to `PUBLIC`.
- **Mutation-check each guard:** break it in the migration, run the test, see it fail, put
  it back.

## 6. Run it

From the repository root, `./dev/run.sh test`. It starts Postgres, runs the bootstrap and
`alembic upgrade head`, then the API checks and tests with the database (they can't be
skipped there), then the web checks. Then check the downgrade against that local database:

```sh
. .dev/secrets.env
cd services/api
export POPSHOT_MIGRATION_DATABASE_URL="postgresql+psycopg://popshot_migrator:${POPSHOT_DEV_MIGRATOR_PASSWORD}@127.0.0.1:54329/popshot"
uv run alembic downgrade base && uv run alembic upgrade head
```
