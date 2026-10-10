# 0002: Group isolation with Postgres Row-Level Security

- Status: accepted
- Date: 2026-10-10

## Context

Groups must never see each other's data unless a lead adds someone. A single missing `WHERE group_id = ...` in application code would break that promise silently, and such bugs are easy to write and hard to spot in review.

## Decision

Enforce isolation in the database:

1. Every table holding group data has a non-null `group_id`.
2. `ENABLE ROW LEVEL SECURITY` and `FORCE ROW LEVEL SECURITY` on each such table.
3. The API connects as `popshot_app`, a login role that owns no tables, has no `BYPASSRLS`, and has only the table privileges it needs.
4. Migrations run as a separate owner role that the running API never uses.
5. At the start of each transaction the API sets `SET LOCAL app.user_id`. Policies check membership through a `SECURITY DEFINER` helper function with a fixed `search_path`, which avoids recursive policy evaluation on the membership table.
6. If `app.user_id` is not set, policies match nothing. Missing context fails closed.

## Testing

An isolation suite runs against a real Postgres in CI. For every protected table it checks that a member of group B cannot select, insert, update or delete group A's rows, including by direct ID, and that a user with no context sees nothing. New tables must be added to the suite.

## Consequences

- Isolation holds even if application code has a bug.
- Every query depends on the transaction-scoped setting, so connection handling must always set it inside a transaction. `SET LOCAL` guarantees it doesn't leak to the next request on a pooled connection.
- Cross-group features (the personal dashboard) work naturally: the user sees every group they belong to and nothing else.
