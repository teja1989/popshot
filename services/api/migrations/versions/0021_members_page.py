"""The members page: guest names in leads' hands, and a push for join requests.

Revision ID: 0021
Revises: 0020
Create Date: 2026-10-12

Players. Until now any active member could rename any player in their group, including
other members (0001's app_member_all; only the API held back). Now, by row-level security:
you rename your own player (routes/me.py does, when you change your name), and a lead or
co-lead renames guests. Removing a guest goes through app_remove_guest, which refuses a
guest who is in any game, so no game ever loses a player (deleting one would cascade).

Join requests. Someone who asks to join through a link is 'pending' and shares no active
group with the leads, so app_push_targets (0006) can't reach them. app_claim_join_request_push
returns the devices of the group's lead and co-leads, once per request
(group_members.request_pushed_at), unless they turned 'requests' off.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "popshot_app"
FUNCTIONS = ["app_remove_guest(uuid)", "app_claim_join_request_push(uuid)"]
OLD_CATEGORIES = "'games', 'play_nights', 'tab', 'milestones', 'recaps', 'invites'"
NEW_CATEGORIES = f"{OLD_CATEGORIES}, 'requests'"

UPGRADE = f"""
DROP POLICY app_member_all ON players;
CREATE POLICY app_member_select ON players FOR SELECT TO {APP_ROLE}
    USING (app_is_member(group_id));
-- Guests by any member; a member's own player when a lead or co-lead lets them in.
CREATE POLICY app_member_insert ON players FOR INSERT TO {APP_ROLE}
    WITH CHECK (app_is_member(group_id)
                AND (user_id IS NULL OR app_is_admin(group_id)));
CREATE POLICY app_rename ON players FOR UPDATE TO {APP_ROLE}
    USING (app_is_member(group_id)
           AND (user_id = app_current_user_id()
                OR (user_id IS NULL AND app_is_admin(group_id))))
    WITH CHECK (app_is_member(group_id)
                AND (user_id = app_current_user_id()
                     OR (user_id IS NULL AND app_is_admin(group_id))));
CREATE POLICY owner_definer_delete ON players FOR DELETE TO CURRENT_USER USING (true);
-- app_remove_guest locks the guest's row first (FOR UPDATE needs an UPDATE policy), so a
-- game can't be logged with them while they're being removed.
CREATE POLICY owner_definer_lock ON players FOR UPDATE TO CURRENT_USER USING (true);

ALTER TABLE notification_settings DROP CONSTRAINT notification_settings_muted_check;
ALTER TABLE notification_settings ADD CONSTRAINT notification_settings_muted_check
    CHECK (muted <@ ARRAY[{NEW_CATEGORIES}]::text[]);

ALTER TABLE group_members ADD COLUMN request_pushed_at timestamptz;

-- Remove a guest who isn't in any game, for a lead or co-lead. Returns 'removed',
-- 'in_games', or 'not_found' (no such guest here, or not a lead or co-lead).
CREATE FUNCTION app_remove_guest(guest uuid) RETURNS text
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    target public.players%ROWTYPE;
BEGIN
    SELECT p.* INTO target FROM public.players p
    WHERE p.id = guest AND p.user_id IS NULL
    FOR UPDATE;
    IF NOT FOUND OR NOT public.app_is_admin(target.group_id) THEN
        RETURN 'not_found';
    END IF;
    IF EXISTS (SELECT 1 FROM public.match_players mp WHERE mp.player_id = guest) THEN
        RETURN 'in_games';
    END IF;
    DELETE FROM public.players p WHERE p.id = guest;
    INSERT INTO public.audit_log (group_id, actor_user_id, action, target_id)
    VALUES (target.group_id, public.app_current_user_id(), 'player.guest_removed', guest);
    RETURN 'removed';
END;
$$;

-- For someone who just asked to join `target_group`: its lead's and co-leads' devices,
-- once per request, leaving out anyone who turned join requests off. With the group's
-- name and the asker's, for the message.
CREATE FUNCTION app_claim_join_request_push(target_group uuid)
RETURNS TABLE (endpoint text, p256dh text, auth text, group_name text, asker text)
LANGUAGE sql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    WITH claimed AS (
        UPDATE public.group_members gm SET request_pushed_at = now()
        WHERE gm.group_id = target_group AND gm.user_id = public.app_current_user_id()
          AND gm.status = 'pending'
          AND (gm.request_pushed_at IS NULL OR gm.request_pushed_at < gm.updated_at)
        RETURNING gm.group_id, gm.user_id
    )
    SELECT s.endpoint, s.p256dh, s.auth, g.name, u.display_name
    FROM claimed c
    JOIN public.groups g ON g.id = c.group_id AND g.deleted_at IS NULL
    JOIN public.users u ON u.id = c.user_id
    JOIN public.group_members leads
      ON leads.group_id = c.group_id AND leads.status = 'active'
     AND leads.role IN ('lead', 'co_lead')
    JOIN public.push_subscriptions s ON s.user_id = leads.user_id
    LEFT JOIN public.notification_settings ns ON ns.user_id = leads.user_id
    WHERE NOT ('requests' = ANY(coalesce(ns.muted, '{{}}')))
$$;
"""


def upgrade() -> None:
    op.execute(UPGRADE)
    for signature in FUNCTIONS:
        op.execute(f"REVOKE EXECUTE ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO {APP_ROLE}")


def downgrade() -> None:
    for signature in reversed(FUNCTIONS):
        op.execute(f"DROP FUNCTION {signature}")
    op.execute("ALTER TABLE group_members DROP COLUMN request_pushed_at")
    # Development and tests only (see 0014): forget anyone's muted requests first.
    op.execute(
        "CREATE POLICY downgrade_0021 ON notification_settings FOR UPDATE TO CURRENT_USER "
        "USING (true) WITH CHECK (true)"
    )
    op.execute("UPDATE notification_settings SET muted = array_remove(muted, 'requests')")
    op.execute("DROP POLICY downgrade_0021 ON notification_settings")
    op.execute(
        "ALTER TABLE notification_settings DROP CONSTRAINT notification_settings_muted_check"
    )
    op.execute(
        "ALTER TABLE notification_settings ADD CONSTRAINT notification_settings_muted_check "
        f"CHECK (muted <@ ARRAY[{OLD_CATEGORIES}]::text[])"
    )
    op.execute("DROP POLICY owner_definer_lock ON players")
    op.execute("DROP POLICY owner_definer_delete ON players")
    op.execute("DROP POLICY app_rename ON players")
    op.execute("DROP POLICY app_member_insert ON players")
    op.execute("DROP POLICY app_member_select ON players")
    op.execute(
        f"CREATE POLICY app_member_all ON players FOR ALL TO {APP_ROLE} "
        "USING (app_is_member(group_id)) WITH CHECK (app_is_member(group_id))"
    )
