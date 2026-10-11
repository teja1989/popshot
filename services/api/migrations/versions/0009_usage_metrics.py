"""Usage metrics: which days each person used Popshot, and the numbers built on it.

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-11

user_activity is one row per person per day they made any signed-in request: the user and
the date, nothing else (no IP address, device or browser). The API writes today's row for
the caller as part of the request; it can't read the table, not even its own rows.
Everything else the metrics need (games, play nights, answers, joins, devices with
notifications on) is already in its own table with a timestamp, so there's no second event
stream that could drift from what actually happened.

The metric functions are owner-only for now: no role is granted them. The super admin page
(next) will get its own narrow grant. Activity older than 13 months is deleted by the
scheduled job.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "popshot_app"
JOBS_ROLE = "popshot_jobs"
OWNER_ONLY = ["app_metrics_weekly(integer)", "app_metrics_retention(integer)"]
PURGE = "app_jobs_purge_activity()"

UPGRADE = f"""
CREATE TABLE user_activity (
    user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    day date NOT NULL,
    PRIMARY KEY (user_id, day)
);
CREATE INDEX user_activity_day_idx ON user_activity (day);

ALTER TABLE user_activity ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_activity FORCE ROW LEVEL SECURITY;
REVOKE ALL ON user_activity FROM PUBLIC;

-- The API records today for the caller, and nothing else.
CREATE POLICY app_record_today ON user_activity FOR INSERT TO {APP_ROLE}
    WITH CHECK (user_id = app_current_user_id() AND day = current_date);
GRANT INSERT ON user_activity TO {APP_ROLE};

CREATE POLICY owner_definer_read ON user_activity FOR SELECT TO CURRENT_USER USING (true);
CREATE POLICY owner_definer_delete ON user_activity FOR DELETE TO CURRENT_USER USING (true);
-- The metrics count members, games and answers across all groups.
CREATE POLICY owner_definer_read ON matches FOR SELECT TO CURRENT_USER USING (true);

CREATE FUNCTION {PURGE} RETURNS integer
LANGUAGE sql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    WITH gone AS (
        DELETE FROM public.user_activity WHERE day < current_date - interval '13 months'
        RETURNING 1
    )
    SELECT count(*)::integer FROM gone
$$;

-- Per week (Monday, UTC), the last `weeks` weeks, oldest first:
--   active_users: people who used the app that week
--   new_users: people who signed up that week
--   active_crews: live groups that logged a game or had a play night that week
--   games, nights, answers: games logged, play nights held, RSVPs given that week
CREATE FUNCTION app_metrics_weekly(weeks integer)
RETURNS TABLE (week_start date, active_users integer, new_users integer,
               active_crews integer, games integer, nights integer, answers integer)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    WITH w AS (
        SELECT generate_series(
            date_trunc('week', now() AT TIME ZONE 'UTC')::date - 7 * (least(weeks, 104) - 1),
            date_trunc('week', now() AT TIME ZONE 'UTC')::date,
            interval '7 days'
        )::date AS week_start
    )
    SELECT w.week_start,
        (SELECT count(DISTINCT a.user_id) FROM public.user_activity a
          WHERE a.day >= w.week_start AND a.day < w.week_start + 7)::integer,
        (SELECT count(*) FROM public.users u
          WHERE u.created_at >= w.week_start AND u.created_at < w.week_start + 7)::integer,
        (SELECT count(DISTINCT g.id) FROM public.groups g
          WHERE g.deleted_at IS NULL AND (
            EXISTS (SELECT 1 FROM public.matches m WHERE m.group_id = g.id
                    AND m.played_at >= w.week_start AND m.played_at < w.week_start + 7)
            OR EXISTS (SELECT 1 FROM public.play_nights n WHERE n.group_id = g.id
                    AND n.cancelled_at IS NULL
                    AND n.starts_at >= w.week_start AND n.starts_at < w.week_start + 7)))::integer,
        (SELECT count(*) FROM public.matches m
          WHERE m.created_at >= w.week_start AND m.created_at < w.week_start + 7)::integer,
        (SELECT count(*) FROM public.play_nights n
          WHERE n.cancelled_at IS NULL
            AND n.starts_at >= w.week_start AND n.starts_at < w.week_start + 7)::integer,
        (SELECT count(*) FROM public.play_night_rsvps r
          WHERE r.updated_at >= w.week_start AND r.updated_at < w.week_start + 7)::integer
    FROM w
    ORDER BY w.week_start
$$;

-- Retention by signup week: of the people who signed up in a week, how many used the app
-- again 1, 2, 3 and 4 weeks later. The last `weeks` cohorts, oldest first.
CREATE FUNCTION app_metrics_retention(weeks integer)
RETURNS TABLE (cohort_week date, signed_up integer,
               week_1 integer, week_2 integer, week_3 integer, week_4 integer)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    WITH cohort AS (
        SELECT u.id, date_trunc('week', u.created_at AT TIME ZONE 'UTC')::date AS week
        FROM public.users u
        WHERE u.created_at >= date_trunc('week', now() AT TIME ZONE 'UTC')
                              - make_interval(weeks => least(weeks, 52) - 1)
    ),
    seen AS (
        SELECT c.id, (a.day - c.week) / 7 AS weeks_later
        FROM cohort c JOIN public.user_activity a ON a.user_id = c.id
    )
    SELECT c.week, count(DISTINCT c.id)::integer,
        (count(DISTINCT s.id) FILTER (WHERE s.weeks_later = 1))::integer,
        (count(DISTINCT s.id) FILTER (WHERE s.weeks_later = 2))::integer,
        (count(DISTINCT s.id) FILTER (WHERE s.weeks_later = 3))::integer,
        (count(DISTINCT s.id) FILTER (WHERE s.weeks_later = 4))::integer
    FROM cohort c
    LEFT JOIN seen s ON s.id = c.id
    GROUP BY c.week
    ORDER BY c.week
$$;
"""


def upgrade() -> None:
    op.execute(UPGRADE)
    for signature in [*OWNER_ONLY, PURGE]:
        op.execute(f"REVOKE EXECUTE ON FUNCTION {signature} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {PURGE} TO {JOBS_ROLE}")


def downgrade() -> None:
    for signature in [*OWNER_ONLY, PURGE]:
        op.execute(f"DROP FUNCTION {signature}")
    op.execute("DROP POLICY owner_definer_read ON matches")
    op.execute("DROP TABLE user_activity")
