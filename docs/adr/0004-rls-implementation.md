# 0004: How row-level security is implemented

- Status: accepted; point 1 refined by [ADR 0005](0005-database-login.md)
- Date: 2026-10-10

## Context

ADR 0002 decided to enforce group isolation with forced Postgres RLS. Building it raised a few
questions that ADR 0002 doesn't answer, and the answers affect what future migrations must do.

## Decision

1. **Roles live outside migrations.** `popshot_owner` (runs migrations, owns everything) and
   `popshot_app` (the API) are created by infrastructure code in Google Cloud and by
   `services/api/db/init_roles.sql` locally and in CI. Migrations only grant. Neither role
   is a superuser or has `BYPASSRLS`; `popshot_app` is not a member of any other role.
2. **The API refuses to start with a risky role.** At startup it checks that it is connected
   as `popshot_app` and that neither that role nor any role it belongs to is a superuser, has
   `BYPASSRLS` or `CREATEROLE`, or owns any table or function.
3. **No role needs `BYPASSRLS`.** Because RLS is forced, the owner is also subject to policies.
   The `SECURITY DEFINER` helpers run as the owner, so the owner gets narrow policies
   (`TO CURRENT_USER`) only for what those helpers read or write. It can't, for example,
   read matches without a user context. We don't know yet whether Cloud SQL lets us grant
   `BYPASSRLS`, and with this design it doesn't matter.
4. **The context is set with `set_config('app.user_id', $1, true)`.** This is the function
   form of `SET LOCAL`: transaction-scoped, and it takes a bound parameter.
5. **Rows can't change groups.** `popshot_app` never gets `UPDATE` on `group_id` or other
   identity columns.
6. **Composite foreign keys.** Child rows reference parents with `(id, group_id)`. Foreign key
   checks bypass RLS, so a plain `id` foreign key would let a member of one group attach
   another group's rows by guessing IDs.
7. **Joining and creating go through functions.** `popshot_app` cannot insert into `groups`
   or `group_members`. `app_create_group` and `app_redeem_invite` are the only ways in.
8. **Roles inside a group are enforced in the database too.** Only leads and co-leads can
   change the group, its members and its invites; only the lead can delete it. Members can
   leave. `audit_log` is append-only. Finer workflow rules (who confirms a match, the 48-hour
   auto-confirm) live in the API.
9. **History isn't deleted piecemeal.** Membership and player rows are never deleted on
   their own; people become `removed`. Their foreign keys cascade, so deleting a whole group
   removes everything in it.

## Consequences

- A new group table needs: `group_id`, composite foreign keys, `ENABLE` + `FORCE` RLS,
  policies for `popshot_app`, column-scoped grants without `group_id`, and an entry in
  `tests/db/test_isolation.py`. The migration template and the catalog tests check for this.
- A future migration that has to read or change data as the owner needs its own owner
  policy, which makes that access visible in review.
- RLS protects against queries that forget a filter. It does not protect against arbitrary
  SQL run as `popshot_app` (for example through SQL injection), which could set
  `app.user_id` itself. Queries must keep using bound parameters.
- On Cloud SQL, users created through the Cloud SQL API join `cloudsqlsuperuser`. The
  `popshot_app` role must be created with SQL instead, or the startup check will refuse it.
