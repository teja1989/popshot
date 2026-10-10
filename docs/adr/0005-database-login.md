# 0005: Database login with IAM and group roles

- Status: accepted
- Date: 2026-10-10
- Refines: ADR 0004, point 1

## Context

ADR 0004 had two login roles, `popshot_owner` and `popshot_app`, with passwords. On Cloud SQL
we'd rather have no database passwords at all, and Cloud SQL supports logging in as a service
account's IAM user with a short-lived OAuth token.

## Decision

1. `popshot_owner` and `popshot_app` become **NOLOGIN group roles**. Policies, grants and
   ownership target them exactly as before.
2. Login users are separate and belong to exactly one group:
   - the migrator (on Cloud SQL, the migration job's service account) is a member of
     `popshot_owner` with INHERIT and SET. Migrations `SET ROLE popshot_owner` first, so
     everything they create is owned by the group role.
   - the API (on Cloud SQL, the API's service account) is a member of `popshot_app` with
     INHERIT only. It can't `SET ROLE` to anything.
3. On Cloud SQL the API and the migrator log in with **IAM database authentication**: the
   password is an access token from the metadata server, fetched when a new connection
   opens. No database password exists for them anywhere.
4. One idempotent bootstrap, `python -m popshot_api.ops.bootstrap_db`, creates the group
   roles, grants membership, makes `popshot_owner` the database owner and locks down the
   `public` schema. It runs as an admin: locally a superuser, in CI and on Cloud SQL a
   non-superuser with CREATEROLE and CREATEDB. CI uses the same non-superuser setup, so the
   Cloud SQL path is tested on every run.
5. The API's startup check now requires the login user to inherit `popshot_app`, not belong to
   `popshot_owner`, and have no unsafe role anywhere in its memberships.

## Consequences

- The only database password is Cloud SQL's built-in admin (`postgres`), used by the
  bootstrap job. It lives in Secret Manager and is never mounted into the API.
- If Cloud SQL ever gave the IAM users extra rights (for example `cloudsqlsuperuser`), the
  startup check would refuse to run rather than silently weaken isolation.
- Locally the login users have passwords (`db/local_login_users.sql`); the rest is identical.
