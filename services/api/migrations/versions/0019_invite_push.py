"""A push when a crew invites you, and an "Invites" switch to turn it off.

Revision ID: 0019
Revises: 0018
Create Date: 2026-10-12

The person invited isn't in the crew, so app_push_targets (0006), which only reaches people
who share a crew with the sender, can't reach them. app_claim_invite_push does one narrow
thing instead: for the open invite the current user just sent, it returns the invitee's
devices once, and only if the invite will actually reach them (not 'silenced' because they
declined lately or blocked the crew) and they haven't turned invites off. direct_invites
.pushed_at records the push, so sending an invite again never pushes again.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "popshot_app"
FUNCTION = "app_claim_invite_push(uuid, uuid)"
OLD_CATEGORIES = "'games', 'play_nights', 'tab', 'milestones', 'recaps'"
NEW_CATEGORIES = f"{OLD_CATEGORIES}, 'invites'"

UPGRADE = f"""
ALTER TABLE notification_settings DROP CONSTRAINT notification_settings_muted_check;
ALTER TABLE notification_settings ADD CONSTRAINT notification_settings_muted_check
    CHECK (muted <@ ARRAY[{NEW_CATEGORIES}]::text[]);

ALTER TABLE direct_invites ADD COLUMN pushed_at timestamptz;

-- The invitee's devices for the open invite the current user sent `invitee` in
-- `target_group`, the first time only; nothing if it's silenced or they muted invites.
CREATE FUNCTION {FUNCTION.replace("uuid, uuid", "target_group uuid, invitee uuid")}
RETURNS TABLE (endpoint text, p256dh text, auth text)
LANGUAGE sql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    WITH claimed AS (
        UPDATE public.direct_invites d SET pushed_at = now()
        WHERE d.group_id = target_group AND d.user_id = invitee
          AND d.invited_by = public.app_current_user_id()
          AND d.status = 'pending' AND d.expires_at > now() AND d.pushed_at IS NULL
          AND public.app_is_admin(target_group)
        RETURNING d.user_id
    )
    SELECT s.endpoint, s.p256dh, s.auth
    FROM claimed c
    JOIN public.push_subscriptions s ON s.user_id = c.user_id
    LEFT JOIN public.notification_settings ns ON ns.user_id = c.user_id
    WHERE NOT ('invites' = ANY(coalesce(ns.muted, '{{}}')))
$$;
"""


def upgrade() -> None:
    op.execute(UPGRADE)
    op.execute(f"REVOKE EXECUTE ON FUNCTION {FUNCTION} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {FUNCTION} TO {APP_ROLE}")


def downgrade() -> None:
    op.execute(f"DROP FUNCTION {FUNCTION}")
    op.execute("ALTER TABLE direct_invites DROP COLUMN pushed_at")
    # Development and tests only (see 0014): forget anyone's muted invites first.
    op.execute(
        "CREATE POLICY downgrade_0019 ON notification_settings FOR UPDATE TO CURRENT_USER "
        "USING (true) WITH CHECK (true)"
    )
    op.execute("UPDATE notification_settings SET muted = array_remove(muted, 'invites')")
    op.execute("DROP POLICY downgrade_0019 ON notification_settings")
    op.execute(
        "ALTER TABLE notification_settings DROP CONSTRAINT notification_settings_muted_check"
    )
    op.execute(
        "ALTER TABLE notification_settings ADD CONSTRAINT notification_settings_muted_check "
        f"CHECK (muted <@ ARRAY[{OLD_CATEGORIES}]::text[])"
    )
