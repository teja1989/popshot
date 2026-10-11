"""Admin lookup: find a person, see a person, see a crew. Read-only.

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-11

Like 0010's functions, these have no admin check of their own: the API calls them only from
the admin routes, after its allowlist and recent-sign-in check. They return names, roles,
dates and counts: no scores, reflections, answers or devices beyond a count. Emails aren't
stored here at all; the API looks them up from Firebase when an admin opens a person.

admin_views gains target_id: which person or crew was opened.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "popshot_app"
FUNCTIONS = [
    "app_admin_people(text, text)",
    "app_admin_person(uuid)",
    "app_admin_person_groups(uuid)",
    "app_admin_group(uuid)",
    "app_admin_group_members(uuid)",
]

UPGRADE = """
ALTER TABLE admin_views ADD COLUMN target_id uuid;
GRANT INSERT (target_id) ON admin_views TO popshot_app;

-- Games each member played need match_players.
CREATE POLICY owner_definer_read ON match_players FOR SELECT TO CURRENT_USER USING (true);

-- People whose name contains `q` (any case), whose id is `q`, or whose sign-in subject is
-- `subject` (from an email lookup). Most recently active first, at most 50.
CREATE FUNCTION app_admin_people(q text, subject text)
RETURNS TABLE (id uuid, display_name text, avatar_url text, created_at timestamptz,
               last_active date, groups integer)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT u.id, u.display_name, u.avatar_url, u.created_at,
        (SELECT max(a.day) FROM public.user_activity a WHERE a.user_id = u.id),
        (SELECT count(*) FROM public.group_members m
          JOIN public.groups g ON g.id = m.group_id AND g.deleted_at IS NULL
          WHERE m.user_id = u.id AND m.status = 'active')::integer
    FROM public.users u
    WHERE (subject IS NOT NULL AND u.auth_subject = subject)
       OR (q IS NOT NULL AND (u.id::text = lower(q)
                              OR strpos(lower(u.display_name), lower(q)) > 0))
    ORDER BY 5 DESC NULLS LAST, u.created_at DESC
    LIMIT 50
$$;

CREATE FUNCTION app_admin_person(person uuid)
RETURNS TABLE (id uuid, auth_subject text, display_name text, avatar_url text,
               created_at timestamptz, self_level text, last_active date,
               active_days_30 integer, push_devices integer)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT u.id, u.auth_subject, u.display_name, u.avatar_url, u.created_at,
        u.self_level::text,
        (SELECT max(a.day) FROM public.user_activity a WHERE a.user_id = u.id),
        (SELECT count(*) FROM public.user_activity a
          WHERE a.user_id = u.id AND a.day > current_date - 30)::integer,
        (SELECT count(*) FROM public.push_subscriptions s WHERE s.user_id = u.id)::integer
    FROM public.users u
    WHERE u.id = person
$$;

-- Every crew they've been in, including ones they left or were removed from.
CREATE FUNCTION app_admin_person_groups(person uuid)
RETURNS TABLE (group_id uuid, name text, role text, status text, left_on_own boolean,
               joined_at timestamptz, deleted_at timestamptz, games integer)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT g.id, g.name, m.role::text, m.status::text, m.left_at IS NOT NULL,
        m.created_at, g.deleted_at,
        (SELECT count(*) FROM public.players p
          JOIN public.match_players mp ON mp.player_id = p.id
          WHERE p.group_id = g.id AND p.user_id = person)::integer
    FROM public.group_members m
    JOIN public.groups g ON g.id = m.group_id
    WHERE m.user_id = person
    ORDER BY m.status = 'active' DESC, g.deleted_at IS NULL DESC, m.created_at DESC
$$;

CREATE FUNCTION app_admin_group(target uuid)
RETURNS TABLE (id uuid, name text, created_at timestamptz, created_by uuid,
               deleted_at timestamptz, members integer, pending integer, guests integer,
               games integer, last_game_at timestamptz, upcoming_nights integer,
               open_invites integer)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT g.id, g.name, g.created_at, g.created_by, g.deleted_at,
        (SELECT count(*) FROM public.group_members m
          WHERE m.group_id = g.id AND m.status = 'active')::integer,
        (SELECT count(*) FROM public.group_members m
          WHERE m.group_id = g.id AND m.status = 'pending')::integer,
        (SELECT count(*) FROM public.players p
          WHERE p.group_id = g.id AND p.user_id IS NULL)::integer,
        (SELECT count(*) FROM public.matches x WHERE x.group_id = g.id)::integer,
        (SELECT max(x.played_at) FROM public.matches x WHERE x.group_id = g.id),
        (SELECT count(*) FROM public.play_nights n
          WHERE n.group_id = g.id AND n.cancelled_at IS NULL
            AND n.starts_at > now())::integer,
        (SELECT count(*) FROM public.group_invites i
          WHERE i.group_id = g.id AND i.revoked_at IS NULL AND i.expires_at > now()
            AND i.use_count < i.max_uses)::integer
    FROM public.groups g
    WHERE g.id = target
$$;

-- Everyone who has been a member: leads first, then by when they joined.
CREATE FUNCTION app_admin_group_members(target uuid)
RETURNS TABLE (user_id uuid, display_name text, avatar_url text, role text, status text,
               left_on_own boolean, joined_at timestamptz, games integer)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT u.id, u.display_name, u.avatar_url, m.role::text, m.status::text,
        m.left_at IS NOT NULL, m.created_at,
        (SELECT count(*) FROM public.players p
          JOIN public.match_players mp ON mp.player_id = p.id
          WHERE p.group_id = target AND p.user_id = u.id)::integer
    FROM public.group_members m
    JOIN public.users u ON u.id = m.user_id
    WHERE m.group_id = target
    ORDER BY m.status = 'active' DESC, m.role, m.created_at
$$;
"""


def upgrade() -> None:
    op.execute(UPGRADE)
    for signature in FUNCTIONS:
        op.execute(f"REVOKE EXECUTE ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO {APP_ROLE}")


def downgrade() -> None:
    for signature in FUNCTIONS:
        op.execute(f"DROP FUNCTION {signature}")
    op.execute("DROP POLICY owner_definer_read ON match_players")
    op.execute("REVOKE INSERT (target_id) ON admin_views FROM popshot_app")
    op.execute("ALTER TABLE admin_views DROP COLUMN target_id")
