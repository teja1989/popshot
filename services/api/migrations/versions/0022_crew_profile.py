"""A crew profile: a short "about", usual play times, and home courts.

Revision ID: 0022
Revises: 0021
Create Date: 2026-10-13

Leads and co-leads edit it (the groups UPDATE policy already allows only them). People who
aren't in the crew yet see "about" and the usual times, so they know what they're joining:
on an invite link's preview (app_preview_invite) and in their invites (app_my_direct_invites).
Home courts are for members only; neither function returns them.

"About" and court names can't hold links, web or email addresses: they're shown to people
outside the crew, and a link in an invite is a way to phish.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "popshot_app"
DAYS = "'mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'"
TIMES = "'morning', 'midday', 'evening'"
# PostgreSQL's regular expressions: \y is a word boundary.
NO_LINKS = (
    r"'(https?://|www\.|[[:alnum:]._%+-]+@[[:alnum:]-]+\.[[:alpha:]]|"
    r"\y[[:alnum:]-]+\.(com|net|org|io|app|co|ly|me|gg|xyz|info|biz|link|site)\y)'"
)

UPGRADE = f"""
ALTER TABLE groups
    ADD COLUMN about text CHECK (char_length(about) BETWEEN 1 AND 200 AND about !~* {NO_LINKS}),
    ADD COLUMN usual_days text[] NOT NULL DEFAULT '{{}}'
        CHECK (usual_days <@ ARRAY[{DAYS}]::text[]),
    ADD COLUMN usual_times text[] NOT NULL DEFAULT '{{}}'
        CHECK (usual_times <@ ARRAY[{TIMES}]::text[]),
    ADD COLUMN home_courts text[] NOT NULL DEFAULT '{{}}'
        CHECK (cardinality(home_courts) <= 3
               AND char_length(array_to_string(home_courts, '')) <= 240
               AND array_to_string(home_courts, ' ') !~* {NO_LINKS});
GRANT UPDATE (about, usual_days, usual_times, home_courts) ON groups TO {APP_ROLE};

-- 0005's version, plus the crew's "about" and usual times (never its courts).
DROP FUNCTION app_preview_invite(bytea);
CREATE FUNCTION app_preview_invite(invite_token_hash bytea)
RETURNS TABLE (group_id uuid, group_name text, invited_by text, my_status member_status,
               about text, usual_days text[], usual_times text[])
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT CASE WHEN m.status IN ('active', 'pending') THEN g.id END,
           g.name, u.display_name, m.status, g.about, g.usual_days, g.usual_times
    FROM public.group_invites i
    JOIN public.groups g ON g.id = i.group_id
    JOIN public.users u ON u.id = i.created_by
    LEFT JOIN public.group_members m
           ON m.group_id = i.group_id AND m.user_id = public.app_current_user_id()
          AND m.left_at IS NULL
    WHERE public.app_current_user_id() IS NOT NULL
      AND i.token_hash = invite_token_hash
      AND g.deleted_at IS NULL
      AND (m.status IS NOT NULL
           OR (i.revoked_at IS NULL AND i.expires_at > now() AND i.use_count < i.max_uses))
$$;

-- 0018's version, plus the crew's "about" and usual times (never its courts).
DROP FUNCTION app_my_direct_invites();
CREATE FUNCTION app_my_direct_invites()
RETURNS TABLE (id uuid, group_id uuid, group_name text, invited_by_name text,
               members bigint, created_at timestamptz, expires_at timestamptz,
               about text, usual_days text[], usual_times text[])
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT d.id, g.id, g.name, inviter.display_name,
           (SELECT count(*) FROM public.group_members m
            WHERE m.group_id = g.id AND m.status = 'active'),
           d.created_at, d.expires_at, g.about, g.usual_days, g.usual_times
    FROM public.direct_invites d
    JOIN public.groups g ON g.id = d.group_id AND g.deleted_at IS NULL
    LEFT JOIN public.users inviter ON inviter.id = d.invited_by
    WHERE d.user_id = public.app_current_user_id()
      AND d.status = 'pending' AND d.expires_at > now()
    ORDER BY d.created_at DESC
$$;
"""

DOWNGRADE = """
DROP FUNCTION app_my_direct_invites();
CREATE FUNCTION app_my_direct_invites()
RETURNS TABLE (id uuid, group_id uuid, group_name text, invited_by_name text,
               members bigint, created_at timestamptz, expires_at timestamptz)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT d.id, g.id, g.name, inviter.display_name,
           (SELECT count(*) FROM public.group_members m
            WHERE m.group_id = g.id AND m.status = 'active'),
           d.created_at, d.expires_at
    FROM public.direct_invites d
    JOIN public.groups g ON g.id = d.group_id AND g.deleted_at IS NULL
    LEFT JOIN public.users inviter ON inviter.id = d.invited_by
    WHERE d.user_id = public.app_current_user_id()
      AND d.status = 'pending' AND d.expires_at > now()
    ORDER BY d.created_at DESC
$$;

DROP FUNCTION app_preview_invite(bytea);
CREATE FUNCTION app_preview_invite(invite_token_hash bytea)
RETURNS TABLE (group_id uuid, group_name text, invited_by text, my_status member_status)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT CASE WHEN m.status IN ('active', 'pending') THEN g.id END,
           g.name, u.display_name, m.status
    FROM public.group_invites i
    JOIN public.groups g ON g.id = i.group_id
    JOIN public.users u ON u.id = i.created_by
    LEFT JOIN public.group_members m
           ON m.group_id = i.group_id AND m.user_id = public.app_current_user_id()
          AND m.left_at IS NULL
    WHERE public.app_current_user_id() IS NOT NULL
      AND i.token_hash = invite_token_hash
      AND g.deleted_at IS NULL
      AND (m.status IS NOT NULL
           OR (i.revoked_at IS NULL AND i.expires_at > now() AND i.use_count < i.max_uses))
$$;
"""

FUNCTIONS = ["app_preview_invite(bytea)", "app_my_direct_invites()"]


def _grant() -> None:
    for signature in FUNCTIONS:
        op.execute(f"REVOKE EXECUTE ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO {APP_ROLE}")


def upgrade() -> None:
    op.execute(UPGRADE)
    _grant()


def downgrade() -> None:
    op.execute(DOWNGRADE)
    _grant()
    op.execute(
        f"REVOKE UPDATE (about, usual_days, usual_times, home_courts) ON groups FROM {APP_ROLE}"
    )
    op.execute(
        "ALTER TABLE groups DROP COLUMN home_courts, DROP COLUMN usual_times, "
        "DROP COLUMN usual_days, DROP COLUMN about"
    )
