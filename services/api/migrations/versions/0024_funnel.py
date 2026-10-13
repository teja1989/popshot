"""The growth funnel: where people came from, anonymous visit counts, and admin-only views.

Revision ID: 0024
Revises: 0023
Create Date: 2026-10-13

signup_sources holds one short label per account: where the person first came from
(an invite link, a shared recap, a community post...). It's its own table, not a users
column, because crewmates can read each other's users rows. Nobody reads it but the admin
functions below and, for their own row only, the person (their data download). The API
records it once, for a new account (under a day old), through app_set_signup_source. When an
account is deleted, its label goes too (a trigger on users.deleted_at).

page_visits counts visits to the pages people arrive on, per day, page and source. Nothing
else: no person, address, device or cookie. The web server adds 1 through app_count_visit,
which accepts only the known pages and sources. They're approximate (anyone can load a page),
so the dashboard treats them as a trend. Rows older than 13 months are deleted by the
scheduled job, like user_activity.

The app_admin_funnel_* functions and app_admin_crew_stages are granted to popshot_admin only
(the admin service, 0012). Each returns counts, except crew stages, which returns crew names
and sizes as app_admin_groups does: no people.

The funnel follows crews (created → a second member within 7 days → a first game within 7
days → 3+ games in the first 7 days → a game in week 2 → a game in week 4) and people
(signed up → in a crew within 7 days → played within 14 days → back in week 2). "Week 2" and
"week 4" only count crews and people old enough to have had them (the *_eligible columns).
Joining a crew is when the person's player row was made (0020): that's when they're in.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "popshot_app"
JOBS_ROLE = "popshot_jobs"
ADMIN_ROLE = "popshot_admin"

# Kept in step with SignupSource and VisitPage in routes/funnel.py (a test checks).
SOURCES = (
    "direct",
    "recap",
    "invite",
    "code",
    "reddit",
    "facebook",
    "nextdoor",
    "poster",
    "court",
    "partner",
    "other",
)
PAGES = ("home", "recap", "recap_try", "invite")


def _sql_list(values: Sequence[str]) -> str:
    return ", ".join(f"'{v}'" for v in values)


APP_FUNCTIONS = [
    "app_set_signup_source(text)",
    "app_my_signup_source()",
    "app_count_visit(text, text)",
]
JOBS_FUNCTIONS = ["app_jobs_purge_visits()"]
ADMIN_FUNCTIONS = [
    "app_admin_funnel_crews(timestamptz, timestamptz)",
    "app_admin_funnel_people(timestamptz, timestamptz)",
    "app_admin_funnel_sources(timestamptz, timestamptz)",
    "app_admin_funnel_loops(timestamptz, timestamptz)",
    "app_admin_crew_stages(integer)",
]

# What the admin functions read across all crews. Some of these already have an owner read
# policy from earlier migrations; another one, under its own name, changes nothing for them.
OWNER_READS = ["players", "match_players", "recap_shares", "direct_invites", "group_invites"]

UPGRADE = f"""
CREATE TABLE signup_sources (
    user_id uuid PRIMARY KEY REFERENCES users (id) ON DELETE CASCADE,
    source text NOT NULL CHECK (source IN ({_sql_list(SOURCES)})),
    recorded_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE signup_sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE signup_sources FORCE ROW LEVEL SECURITY;
REVOKE ALL ON signup_sources FROM PUBLIC;
CREATE POLICY owner_definer_read ON signup_sources FOR SELECT TO CURRENT_USER USING (true);
CREATE POLICY owner_definer_insert ON signup_sources FOR INSERT TO CURRENT_USER
    WITH CHECK (true);
CREATE POLICY owner_definer_delete ON signup_sources FOR DELETE TO CURRENT_USER USING (true);

CREATE TABLE page_visits (
    day date NOT NULL,
    page text NOT NULL CHECK (page IN ({_sql_list(PAGES)})),
    source text NOT NULL CHECK (source IN ({_sql_list(SOURCES)})),
    visits integer NOT NULL DEFAULT 1 CHECK (visits >= 0),
    PRIMARY KEY (day, page, source)
);
ALTER TABLE page_visits ENABLE ROW LEVEL SECURITY;
ALTER TABLE page_visits FORCE ROW LEVEL SECURITY;
REVOKE ALL ON page_visits FROM PUBLIC;
CREATE POLICY owner_definer_read ON page_visits FOR SELECT TO CURRENT_USER USING (true);
CREATE POLICY owner_definer_insert ON page_visits FOR INSERT TO CURRENT_USER WITH CHECK (true);
CREATE POLICY owner_definer_update ON page_visits FOR UPDATE TO CURRENT_USER
    USING (true) WITH CHECK (true);
CREATE POLICY owner_definer_delete ON page_visits FOR DELETE TO CURRENT_USER USING (true);

-- Record where the caller came from: once, and only while their account is new. False if
-- there's no caller, the label is unknown, the account isn't new, or it's already set.
CREATE FUNCTION app_set_signup_source(src text) RETURNS boolean
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    me uuid := public.app_current_user_id();
BEGIN
    IF me IS NULL OR src IS NULL OR src NOT IN ({_sql_list(SOURCES)}) THEN
        RETURN false;
    END IF;
    INSERT INTO public.signup_sources (user_id, source)
    SELECT u.id, src FROM public.users u
    WHERE u.id = me AND u.deleted_at IS NULL AND u.created_at > now() - interval '1 day'
    ON CONFLICT (user_id) DO NOTHING;
    RETURN FOUND;
END;
$$;

-- The caller's own label, for their data download.
CREATE FUNCTION app_my_signup_source() RETURNS text
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT s.source FROM public.signup_sources s
    WHERE s.user_id = public.app_current_user_id()
$$;

-- Add one visit to today's count for a page and source. False for anything unknown.
CREATE FUNCTION app_count_visit(p text, src text) RETURNS boolean
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
    IF p IS NULL OR src IS NULL OR p NOT IN ({_sql_list(PAGES)})
       OR src NOT IN ({_sql_list(SOURCES)}) THEN
        RETURN false;
    END IF;
    INSERT INTO public.page_visits AS v (day, page, source) VALUES (current_date, p, src)
    ON CONFLICT (day, page, source) DO UPDATE SET visits = v.visits + 1;
    RETURN true;
END;
$$;

CREATE FUNCTION app_jobs_purge_visits() RETURNS integer
LANGUAGE sql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    WITH gone AS (
        DELETE FROM public.page_visits WHERE day < current_date - interval '13 months'
        RETURNING 1
    )
    SELECT count(*)::integer FROM gone
$$;

-- A deleted account's label goes with it.
CREATE FUNCTION app_forget_signup_source() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
    DELETE FROM public.signup_sources s WHERE s.user_id = NEW.id;
    RETURN NEW;
END;
$$;
CREATE TRIGGER users_forget_signup_source
    AFTER UPDATE OF deleted_at ON users
    FOR EACH ROW WHEN (NEW.deleted_at IS NOT NULL AND OLD.deleted_at IS NULL)
    EXECUTE FUNCTION app_forget_signup_source();

-- Crews created in [since, until): how far each got. See the docstring for the steps.
CREATE FUNCTION app_admin_funnel_crews(since timestamptz, until timestamptz)
RETURNS TABLE (created integer, second_member integer, first_game integer,
               activated integer, week_2_eligible integer, played_week_2 integer,
               week_4_eligible integer, played_week_4 integer,
               median_hours_to_first_game double precision)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    WITH c AS (
        SELECT g.id, g.created_at,
            (SELECT count(*) FROM public.players p
              WHERE p.group_id = g.id AND p.user_id IS NOT NULL
                AND p.created_at < g.created_at + interval '7 days') AS members_7d,
            (SELECT min(m.created_at) FROM public.matches m WHERE m.group_id = g.id)
                AS first_game_at,
            (SELECT count(*) FROM public.matches m
              WHERE m.group_id = g.id AND m.created_at < g.created_at + interval '7 days')
                AS games_7d,
            EXISTS (SELECT 1 FROM public.matches m WHERE m.group_id = g.id
                    AND m.created_at >= g.created_at + interval '7 days'
                    AND m.created_at < g.created_at + interval '14 days') AS week_2,
            EXISTS (SELECT 1 FROM public.matches m WHERE m.group_id = g.id
                    AND m.created_at >= g.created_at + interval '21 days'
                    AND m.created_at < g.created_at + interval '28 days') AS week_4
        FROM public.groups g
        WHERE g.created_at >= since AND g.created_at < until
    )
    SELECT count(*)::integer,
        (count(*) FILTER (WHERE members_7d >= 2))::integer,
        (count(*) FILTER (WHERE games_7d >= 1))::integer,
        (count(*) FILTER (WHERE games_7d >= 3))::integer,
        (count(*) FILTER (WHERE created_at <= now() - interval '14 days'))::integer,
        (count(*) FILTER (WHERE created_at <= now() - interval '14 days' AND week_2))::integer,
        (count(*) FILTER (WHERE created_at <= now() - interval '28 days'))::integer,
        (count(*) FILTER (WHERE created_at <= now() - interval '28 days' AND week_4))::integer,
        percentile_cont(0.5) WITHIN GROUP (
            ORDER BY extract(epoch FROM first_game_at - created_at) / 3600
        ) FILTER (WHERE first_game_at IS NOT NULL)
    FROM c
$$;

-- People who signed up in [since, until), deleted accounts left out.
CREATE FUNCTION app_admin_funnel_people(since timestamptz, until timestamptz)
RETURNS TABLE (signed_up integer, in_crew integer, played integer,
               week_2_eligible integer, back_week_2 integer)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    WITH u AS (
        SELECT u.id, u.created_at,
            EXISTS (SELECT 1 FROM public.players p WHERE p.user_id = u.id
                    AND p.created_at < u.created_at + interval '7 days') AS in_crew,
            EXISTS (SELECT 1 FROM public.players p
                    JOIN public.match_players mp ON mp.player_id = p.id
                    JOIN public.matches m ON m.id = mp.match_id
                    WHERE p.user_id = u.id
                      AND m.created_at < u.created_at + interval '14 days') AS played,
            EXISTS (SELECT 1 FROM public.user_activity a WHERE a.user_id = u.id
                    AND a.day >= (u.created_at + interval '7 days')::date
                    AND a.day < (u.created_at + interval '14 days')::date) AS back_week_2
        FROM public.users u
        WHERE u.created_at >= since AND u.created_at < until AND u.deleted_at IS NULL
    )
    SELECT count(*)::integer,
        (count(*) FILTER (WHERE in_crew))::integer,
        (count(*) FILTER (WHERE played))::integer,
        (count(*) FILTER (WHERE created_at <= now() - interval '14 days'))::integer,
        (count(*) FILTER (WHERE created_at <= now() - interval '14 days' AND back_week_2))
            ::integer
    FROM u
$$;

-- The people funnel by where people came from, with the visits that brought them: arrivals
-- on the home page and invite pages. No label means 'direct'.
CREATE FUNCTION app_admin_funnel_sources(since timestamptz, until timestamptz)
RETURNS TABLE (source text, visits integer, signed_up integer, in_crew integer,
               played integer)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    WITH u AS (
        SELECT coalesce(s.source, 'direct') AS source,
            EXISTS (SELECT 1 FROM public.players p WHERE p.user_id = u.id
                    AND p.created_at < u.created_at + interval '7 days') AS in_crew,
            EXISTS (SELECT 1 FROM public.players p
                    JOIN public.match_players mp ON mp.player_id = p.id
                    JOIN public.matches m ON m.id = mp.match_id
                    WHERE p.user_id = u.id
                      AND m.created_at < u.created_at + interval '14 days') AS played
        FROM public.users u
        LEFT JOIN public.signup_sources s ON s.user_id = u.id
        WHERE u.created_at >= since AND u.created_at < until AND u.deleted_at IS NULL
    ),
    v AS (
        SELECT pv.source, sum(pv.visits)::integer AS visits FROM public.page_visits pv
        WHERE pv.page IN ('home', 'invite')
          AND pv.day >= since::date AND pv.day < until::date
        GROUP BY pv.source
    ),
    people AS (
        SELECT u.source, count(*)::integer AS signed_up,
            (count(*) FILTER (WHERE u.in_crew))::integer AS in_crew,
            (count(*) FILTER (WHERE u.played))::integer AS played
        FROM u GROUP BY u.source
    )
    SELECT coalesce(p.source, v.source), coalesce(v.visits, 0), coalesce(p.signed_up, 0),
           coalesce(p.in_crew, 0), coalesce(p.played, 0)
    FROM people p FULL JOIN v ON v.source = p.source
    ORDER BY 3 DESC, 2 DESC, 1
$$;

-- The sharing loops in [since, until): recaps shared → share pages opened → "Try Popshot"
-- taps → sign-ups from a recap; invites sent → accepted, and sign-ups from invite links and
-- codes. Plus the people active in the period, to set those sign-ups against.
CREATE FUNCTION app_admin_funnel_loops(since timestamptz, until timestamptz)
RETURNS TABLE (recaps_shared integer, share_views integer, try_taps integer,
               recap_signups integer, invite_links integer, link_joins integer,
               direct_invites integer, direct_accepted integer, invite_signups integer,
               code_signups integer, active_users integer)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT
        (SELECT count(*) FROM public.recap_shares r
          WHERE r.created_at >= since AND r.created_at < until)::integer,
        (SELECT coalesce(sum(pv.visits), 0) FROM public.page_visits pv
          WHERE pv.page = 'recap' AND pv.day >= since::date AND pv.day < until::date)::integer,
        (SELECT coalesce(sum(pv.visits), 0) FROM public.page_visits pv
          WHERE pv.page = 'recap_try' AND pv.day >= since::date
            AND pv.day < until::date)::integer,
        (SELECT count(*) FROM public.signup_sources s JOIN public.users u ON u.id = s.user_id
          WHERE s.source = 'recap' AND u.created_at >= since AND u.created_at < until)::integer,
        (SELECT count(*) FROM public.group_invites i
          WHERE i.created_at >= since AND i.created_at < until)::integer,
        (SELECT coalesce(sum(i.use_count), 0) FROM public.group_invites i
          WHERE i.created_at >= since AND i.created_at < until)::integer,
        (SELECT count(*) FROM public.direct_invites d
          WHERE d.created_at >= since AND d.created_at < until)::integer,
        (SELECT count(*) FROM public.direct_invites d
          WHERE d.created_at >= since AND d.created_at < until AND d.status = 'accepted')
            ::integer,
        (SELECT count(*) FROM public.signup_sources s JOIN public.users u ON u.id = s.user_id
          WHERE s.source = 'invite' AND u.created_at >= since AND u.created_at < until)
            ::integer,
        (SELECT count(*) FROM public.signup_sources s JOIN public.users u ON u.id = s.user_id
          WHERE s.source = 'code' AND u.created_at >= since AND u.created_at < until)::integer,
        (SELECT count(DISTINCT a.user_id) FROM public.user_activity a
          WHERE a.day >= since::date AND a.day < until::date)::integer
$$;

-- Crews created in the last `days` days (at most 180), newest first, with how far each got.
-- Names and counts only, as app_admin_groups.
CREATE FUNCTION app_admin_crew_stages(days integer)
RETURNS TABLE (id uuid, name text, created_at timestamptz, deleted boolean, members integer,
               games integer, games_first_week integer, first_game_at timestamptz,
               last_game_at timestamptz)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT g.id, g.name, g.created_at, g.deleted_at IS NOT NULL,
        (SELECT count(*) FROM public.group_members m
          WHERE m.group_id = g.id AND m.status = 'active')::integer,
        (SELECT count(*) FROM public.matches m WHERE m.group_id = g.id)::integer,
        (SELECT count(*) FROM public.matches m WHERE m.group_id = g.id
          AND m.created_at < g.created_at + interval '7 days')::integer,
        (SELECT min(m.created_at) FROM public.matches m WHERE m.group_id = g.id),
        (SELECT max(m.created_at) FROM public.matches m WHERE m.group_id = g.id)
    FROM public.groups g
    WHERE g.created_at > now() - make_interval(days => least(greatest(days, 1), 180))
    ORDER BY g.created_at DESC
    LIMIT 300
$$;
"""


def upgrade() -> None:
    op.execute(UPGRADE)
    for table in OWNER_READS:
        op.execute(
            f"CREATE POLICY owner_funnel_read ON {table} FOR SELECT TO CURRENT_USER USING (true)"
        )
    for signature in [*APP_FUNCTIONS, *JOBS_FUNCTIONS, *ADMIN_FUNCTIONS]:
        op.execute(f"REVOKE EXECUTE ON FUNCTION {signature} FROM PUBLIC")
    op.execute("REVOKE EXECUTE ON FUNCTION app_forget_signup_source() FROM PUBLIC")
    for signature in APP_FUNCTIONS:
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO {APP_ROLE}")
    for signature in JOBS_FUNCTIONS:
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO {JOBS_ROLE}")
    for signature in ADMIN_FUNCTIONS:
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO {ADMIN_ROLE}")


def downgrade() -> None:
    for table in OWNER_READS:
        op.execute(f"DROP POLICY owner_funnel_read ON {table}")
    for signature in [*ADMIN_FUNCTIONS, *JOBS_FUNCTIONS, *APP_FUNCTIONS]:
        op.execute(f"DROP FUNCTION {signature}")
    op.execute("DROP TRIGGER users_forget_signup_source ON users")
    op.execute("DROP FUNCTION app_forget_signup_source()")
    op.execute("DROP TABLE page_visits")
    op.execute("DROP TABLE signup_sources")
