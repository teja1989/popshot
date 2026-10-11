"""The admin page: app-wide numbers for the owner, and a record of each time it's opened.

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-11

The API's role can now run the metric functions from 0009 and the two below. Each returns
counts only. app_admin_groups also returns group names, but no people, scores or messages.
Whether someone is an admin is decided by the API (the POPSHOT_ADMIN_EMAILS setting, on a
recent sign-in); these functions have no check of their own, so the API must only call them
from the admin routes.

admin_views records each time the admin page is opened: who and when. The API can add a
row for the caller, and can't read the table.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "popshot_app"
NEW = ["app_admin_totals()", "app_admin_groups()"]
FROM_0009 = ["app_metrics_weekly(integer)", "app_metrics_retention(integer)"]

UPGRADE = f"""
CREATE TABLE admin_views (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    page text NOT NULL CHECK (char_length(page) BETWEEN 1 AND 40),
    viewed_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE admin_views ENABLE ROW LEVEL SECURITY;
ALTER TABLE admin_views FORCE ROW LEVEL SECURITY;
REVOKE ALL ON admin_views FROM PUBLIC;
CREATE POLICY app_record_own ON admin_views FOR INSERT TO {APP_ROLE}
    WITH CHECK (user_id = app_current_user_id());
GRANT INSERT (user_id, page) ON admin_views TO {APP_ROLE};
-- For reviewing it as the owner (from Cloud SQL Studio, say).
CREATE POLICY owner_read ON admin_views FOR SELECT TO CURRENT_USER USING (true);

-- One row of totals across the whole app.
CREATE FUNCTION app_admin_totals()
RETURNS TABLE (users integer, new_users_7d integer, active_users_7d integer,
               active_users_30d integer, live_groups integer, deleted_groups integer,
               games integer, games_30d integer, push_users integer, level_set integer)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT
        (SELECT count(*) FROM public.users)::integer,
        (SELECT count(*) FROM public.users
          WHERE created_at > now() - interval '7 days')::integer,
        (SELECT count(DISTINCT user_id) FROM public.user_activity
          WHERE day > current_date - 7)::integer,
        (SELECT count(DISTINCT user_id) FROM public.user_activity
          WHERE day > current_date - 30)::integer,
        (SELECT count(*) FROM public.groups WHERE deleted_at IS NULL)::integer,
        (SELECT count(*) FROM public.groups WHERE deleted_at IS NOT NULL)::integer,
        (SELECT count(*) FROM public.matches)::integer,
        (SELECT count(*) FROM public.matches
          WHERE created_at > now() - interval '30 days')::integer,
        (SELECT count(DISTINCT user_id) FROM public.push_subscriptions)::integer,
        (SELECT count(*) FROM public.users WHERE self_level IS NOT NULL)::integer
$$;

-- Each live group: size and activity, most recently active first. No member names.
CREATE FUNCTION app_admin_groups()
RETURNS TABLE (id uuid, name text, created_at timestamptz, members integer,
               games integer, games_30d integer, last_game_at timestamptz,
               upcoming_nights integer)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT g.id, g.name, g.created_at,
        (SELECT count(*) FROM public.group_members m
          WHERE m.group_id = g.id AND m.status = 'active')::integer,
        (SELECT count(*) FROM public.matches x WHERE x.group_id = g.id)::integer,
        (SELECT count(*) FROM public.matches x
          WHERE x.group_id = g.id AND x.created_at > now() - interval '30 days')::integer,
        (SELECT max(x.played_at) FROM public.matches x WHERE x.group_id = g.id),
        (SELECT count(*) FROM public.play_nights n
          WHERE n.group_id = g.id AND n.cancelled_at IS NULL
            AND n.starts_at > now())::integer
    FROM public.groups g
    WHERE g.deleted_at IS NULL
    ORDER BY 7 DESC NULLS LAST, g.created_at DESC
    LIMIT 500
$$;
"""


def upgrade() -> None:
    op.execute(UPGRADE)
    for signature in NEW:
        op.execute(f"REVOKE EXECUTE ON FUNCTION {signature} FROM PUBLIC")
    for signature in [*NEW, *FROM_0009]:
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO {APP_ROLE}")


def downgrade() -> None:
    for signature in FROM_0009:
        op.execute(f"REVOKE EXECUTE ON FUNCTION {signature} FROM {APP_ROLE}")
    for signature in NEW:
        op.execute(f"DROP FUNCTION {signature}")
    op.execute("DROP TABLE admin_views")
