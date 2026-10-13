"""The scheduled job tells people who played that their week is ready, on Mondays.

Revision ID: 0026
Revises: 0025
Create Date: 2026-10-13

From 13:00 UTC on Mondays (ops/tick.py), people who played at least one game in the 7 days
before then get one push: "Your week is ready". Nobody who didn't play is nudged.
week_notifications records who has been told for which Monday, before sending, so nobody
is told twice. Like the other job functions (0008, 0016), only popshot_jobs may run it.

week_notifications only ever needs this Monday's rows, so the claim function clears older
weeks as it goes, and a deleted account's rows go with it (a trigger, as in 0024).

Notifications get a new category, 'your_week', so people can turn these off.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0026"
down_revision: str | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JOBS_ROLE = "popshot_jobs"
FUNCTIONS = ["app_jobs_claim_week(date, timestamptz, timestamptz)"]
OLD_CATEGORIES = "'games', 'play_nights', 'tab', 'milestones', 'recaps', 'invites', 'requests'"
NEW_CATEGORIES = f"{OLD_CATEGORIES}, 'your_week'"

UPGRADE = f"""
ALTER TABLE notification_settings DROP CONSTRAINT notification_settings_muted_check;
ALTER TABLE notification_settings ADD CONSTRAINT notification_settings_muted_check
    CHECK (muted <@ ARRAY[{NEW_CATEGORIES}]::text[]);

CREATE TABLE week_notifications (
    user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    -- The Monday it was sent for.
    week date NOT NULL,
    notified_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, week)
);
ALTER TABLE week_notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE week_notifications FORCE ROW LEVEL SECURITY;
REVOKE ALL ON week_notifications FROM PUBLIC;
-- Only the functions below touch it.
CREATE POLICY owner_definer_insert ON week_notifications FOR INSERT TO CURRENT_USER
    WITH CHECK (true);
CREATE POLICY owner_definer_read ON week_notifications FOR SELECT TO CURRENT_USER USING (true);
CREATE POLICY owner_definer_delete ON week_notifications FOR DELETE TO CURRENT_USER
    USING (true);

-- Claims `target_week` for everyone who played a game in [since, until) in a live crew they're
-- still an active member of, hasn't muted 'your_week', and wasn't told yet; returns their
-- devices. Guests have no account, and deleted accounts are left out.
CREATE FUNCTION app_jobs_claim_week(target_week date, since timestamptz, until timestamptz)
RETURNS TABLE (endpoint text, p256dh text, auth text)
LANGUAGE sql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    WITH old AS (
        DELETE FROM public.week_notifications w WHERE w.week < target_week
    ),
    played AS (
        SELECT DISTINCT p.user_id
        FROM public.matches m
        JOIN public.groups g ON g.id = m.group_id AND g.deleted_at IS NULL
        JOIN public.match_players mp ON mp.match_id = m.id
        JOIN public.players p ON p.id = mp.player_id AND p.group_id = m.group_id
        JOIN public.group_members gm
            ON gm.group_id = m.group_id AND gm.user_id = p.user_id AND gm.status = 'active'
        JOIN public.users u ON u.id = p.user_id AND u.deleted_at IS NULL
        LEFT JOIN public.notification_settings ns ON ns.user_id = p.user_id
        WHERE m.played_at >= since AND m.played_at < until
          AND NOT ('your_week' = ANY(coalesce(ns.muted, '{{}}')))
    ),
    claimed AS (
        INSERT INTO public.week_notifications (user_id, week)
        SELECT played.user_id, target_week FROM played
        ON CONFLICT DO NOTHING
        RETURNING user_id
    )
    SELECT s.endpoint, s.p256dh, s.auth
    FROM claimed c
    JOIN public.push_subscriptions s ON s.user_id = c.user_id
$$;

-- A deleted account's claims go with it.
CREATE FUNCTION app_forget_week_notifications() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
    DELETE FROM public.week_notifications w WHERE w.user_id = NEW.id;
    RETURN NEW;
END;
$$;
REVOKE EXECUTE ON FUNCTION app_forget_week_notifications() FROM PUBLIC;
CREATE TRIGGER users_forget_week_notifications
    AFTER UPDATE OF deleted_at ON users
    FOR EACH ROW WHEN (NEW.deleted_at IS NOT NULL AND OLD.deleted_at IS NULL)
    EXECUTE FUNCTION app_forget_week_notifications();
"""


def upgrade() -> None:
    op.execute(UPGRADE)
    for signature in FUNCTIONS:
        op.execute(f"REVOKE EXECUTE ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO {JOBS_ROLE}")


def downgrade() -> None:
    op.execute("DROP TRIGGER users_forget_week_notifications ON users")
    op.execute("DROP FUNCTION app_forget_week_notifications()")
    for signature in FUNCTIONS:
        op.execute(f"DROP FUNCTION {signature}")
    op.execute("DROP TABLE week_notifications")
    # Development and tests only (see 0014): forget anyone's muted 'your_week' first.
    op.execute(
        "CREATE POLICY downgrade_0026 ON notification_settings FOR UPDATE TO CURRENT_USER "
        "USING (true) WITH CHECK (true)"
    )
    op.execute("UPDATE notification_settings SET muted = array_remove(muted, 'your_week')")
    op.execute("DROP POLICY downgrade_0026 ON notification_settings")
    op.execute(
        "ALTER TABLE notification_settings DROP CONSTRAINT notification_settings_muted_check"
    )
    op.execute(
        "ALTER TABLE notification_settings ADD CONSTRAINT notification_settings_muted_check "
        f"CHECK (muted <@ ARRAY[{OLD_CATEGORIES}]::text[])"
    )
