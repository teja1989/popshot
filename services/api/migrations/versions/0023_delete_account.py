"""Deleting your account: asked for in the app, done for good 7 days later.

Revision ID: 0023
Revises: 0022
Create Date: 2026-10-13

You ask (users.delete_requested_at, routes/me.py) and have 7 days to change your mind. Then
the scheduled job (ops/tick.py) deletes your Firebase sign-in, where your email lives, and
calls app_jobs_purge_user.

Your crews' games stay, as the privacy policy says. Deleting the user's memberships would
take games with it: matches, players and match_players all hang off group_members with
ON DELETE CASCADE. So the user row is kept as an empty placeholder instead: named "Former
player", no photo, a sign-in that can never match anyone, marked as having left every crew.
Everything else about them is deleted: devices, notification settings, focus, game notes,
meetup answers, invites, blocks, their code, links they made, and usage days. A crew where
they're the only member is deleted outright. A crew they still lead (someone joined while
they waited) passes to its longest-standing co-lead, or else member.

Only popshot_jobs can run the two job functions, like the other job functions (0008).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "popshot_app"
JOBS_ROLE = "popshot_jobs"
UNDO_DAYS = 7
FUNCTIONS = ["app_jobs_due_deletions()", "app_jobs_purge_user(uuid)"]

# What app_jobs_purge_user needs, beyond what earlier migrations gave the owner.
OWNER_POLICIES = [
    ("owner_definer_update", "users", "UPDATE", "USING (true) WITH CHECK (true)"),
    ("owner_definer_delete", "notification_settings", "DELETE", "USING (true)"),
    ("owner_definer_delete", "user_focus", "DELETE", "USING (true)"),
    ("owner_definer_delete", "match_reflections", "DELETE", "USING (true)"),
    ("owner_definer_delete", "play_night_rsvps", "DELETE", "USING (true)"),
    ("owner_definer_delete", "recap_shares", "DELETE", "USING (true)"),
]

UPGRADE = f"""
ALTER TABLE users
    ADD COLUMN delete_requested_at timestamptz,
    ADD COLUMN deleted_at timestamptz;
GRANT UPDATE (delete_requested_at) ON users TO {APP_ROLE};

-- Accounts whose {UNDO_DAYS} days to change their mind are up, with the Firebase sign-in to
-- delete first.
CREATE FUNCTION app_jobs_due_deletions()
RETURNS TABLE (user_id uuid, auth_subject text)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT u.id, u.auth_subject FROM public.users u
    WHERE u.delete_requested_at <= now() - interval '{UNDO_DAYS} days'
      AND u.deleted_at IS NULL
    ORDER BY u.delete_requested_at
    LIMIT 50
$$;

-- Empty out one account (see the docstring). False if it isn't due (say, they changed
-- their mind since the job looked).
CREATE FUNCTION app_jobs_purge_user(target uuid) RETURNS boolean
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    crew record;
    heir uuid;
BEGIN
    PERFORM 1 FROM public.users u
    WHERE u.id = target AND u.deleted_at IS NULL
      AND u.delete_requested_at <= now() - interval '{UNDO_DAYS} days'
    FOR UPDATE;
    IF NOT FOUND THEN
        RETURN false;
    END IF;

    -- Crews they're the only member of go with them.
    DELETE FROM public.groups g
    WHERE EXISTS (
        SELECT 1 FROM public.group_members m
        WHERE m.group_id = g.id AND m.user_id = target AND m.status = 'active'
    ) AND NOT EXISTS (
        SELECT 1 FROM public.group_members m
        WHERE m.group_id = g.id AND m.user_id <> target AND m.status = 'active'
    );

    -- Crews they still lead pass on: the longest-standing co-lead, or else member.
    FOR crew IN
        SELECT m.group_id FROM public.group_members m
        WHERE m.user_id = target AND m.status = 'active' AND m.role = 'lead'
    LOOP
        SELECT m.user_id INTO heir FROM public.group_members m
        WHERE m.group_id = crew.group_id AND m.user_id <> target AND m.status = 'active'
        ORDER BY m.role = 'co_lead' DESC, m.created_at, m.user_id
        LIMIT 1;
        UPDATE public.group_members m SET role = 'lead', updated_at = now()
        WHERE m.group_id = crew.group_id AND m.user_id = heir;
    END LOOP;

    -- Gone from every crew, but their games stay.
    UPDATE public.group_members m
    SET status = 'removed', role = 'member', left_at = coalesce(m.left_at, now()),
        updated_at = now()
    WHERE m.user_id = target;
    UPDATE public.players p SET display_name = 'Former player' WHERE p.user_id = target;
    UPDATE public.group_invites i SET revoked_at = now()
    WHERE i.created_by = target AND i.revoked_at IS NULL;

    DELETE FROM public.push_subscriptions s WHERE s.user_id = target;
    DELETE FROM public.notification_settings s WHERE s.user_id = target;
    DELETE FROM public.user_focus f WHERE f.user_id = target;
    DELETE FROM public.match_reflections r WHERE r.user_id = target;
    DELETE FROM public.play_night_rsvps r WHERE r.user_id = target;
    DELETE FROM public.user_activity a WHERE a.user_id = target;
    DELETE FROM public.direct_invites d WHERE d.user_id = target;
    UPDATE public.direct_invites d SET invited_by = NULL WHERE d.invited_by = target;
    DELETE FROM public.invite_blocks b WHERE b.user_id = target;
    DELETE FROM public.invite_code_lookups l WHERE l.user_id = target OR l.found_user = target;
    DELETE FROM public.recap_shares s WHERE s.created_by = target;

    UPDATE public.users u
    SET display_name = 'Former player', avatar_url = NULL, self_level = NULL,
        invite_code = NULL, hide_on_shared_cards = true,
        auth_subject = 'deleted:' || u.id::text, deleted_at = now()
    WHERE u.id = target;
    RETURN true;
END;
$$;

-- 0018's app_knows, but never someone whose account is deleted (they'd show as "Former
-- player" to invite).
CREATE OR REPLACE FUNCTION app_knows(target_user uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM public.group_members me
        JOIN public.group_members them ON them.group_id = me.group_id
        JOIN public.users u ON u.id = them.user_id AND u.deleted_at IS NULL
        WHERE me.user_id = public.app_current_user_id()
          AND me.status IN ('active', 'removed')
          AND them.user_id = target_user
          AND them.status IN ('active', 'removed')
          AND them.user_id <> me.user_id
    )
$$;
"""


def upgrade() -> None:
    for name, table, command, rule in OWNER_POLICIES:
        op.execute(f"CREATE POLICY {name} ON {table} FOR {command} TO CURRENT_USER {rule}")
    op.execute(UPGRADE)
    for signature in FUNCTIONS:
        op.execute(f"REVOKE EXECUTE ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO {JOBS_ROLE}")


KNOWS_BEFORE = """
CREATE OR REPLACE FUNCTION app_knows(target_user uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM public.group_members me
        JOIN public.group_members them ON them.group_id = me.group_id
        WHERE me.user_id = public.app_current_user_id()
          AND me.status IN ('active', 'removed')
          AND them.user_id = target_user
          AND them.status IN ('active', 'removed')
          AND them.user_id <> me.user_id
    )
$$;
"""


def downgrade() -> None:
    op.execute(KNOWS_BEFORE)
    for signature in reversed(FUNCTIONS):
        op.execute(f"DROP FUNCTION {signature}")
    op.execute(f"REVOKE UPDATE (delete_requested_at) ON users FROM {APP_ROLE}")
    op.execute("ALTER TABLE users DROP COLUMN deleted_at, DROP COLUMN delete_requested_at")
    for name, table, _, _ in reversed(OWNER_POLICIES):
        op.execute(f"DROP POLICY {name} ON {table}")
