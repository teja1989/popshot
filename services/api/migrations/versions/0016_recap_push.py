"""The scheduled job tells players their recap is ready.

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-12

An hour or more after an outing's last game (popshot_api.recap), the job (ops/tick.py) sends
the people who played a push: "Your recap is ready". recap_notifications records each
outing it has announced, before sending, so nobody is told twice. Like the other job
functions (0008), these do one narrow thing each and only popshot_jobs may run them.

Notifications get a new category, 'recaps', so people can turn these off.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JOBS_ROLE = "popshot_jobs"
FUNCTIONS = [
    "app_jobs_recent_matches(timestamptz)",
    "app_jobs_claim_recap(uuid, uuid)",
    "app_jobs_recap_targets(uuid, uuid[])",
]
OLD_CATEGORIES = "'games', 'play_nights', 'tab', 'milestones'"
NEW_CATEGORIES = f"{OLD_CATEGORIES}, 'recaps'"

UPGRADE = f"""
ALTER TABLE notification_settings DROP CONSTRAINT notification_settings_muted_check;
ALTER TABLE notification_settings ADD CONSTRAINT notification_settings_muted_check
    CHECK (muted <@ ARRAY[{NEW_CATEGORIES}]::text[]);

CREATE TABLE recap_notifications (
    group_id uuid NOT NULL REFERENCES groups (id) ON DELETE CASCADE,
    -- The outing's first match (popshot_api.recap.Outing.key).
    outing_key uuid NOT NULL,
    notified_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (group_id, outing_key)
);
ALTER TABLE recap_notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE recap_notifications FORCE ROW LEVEL SECURITY;
REVOKE ALL ON recap_notifications FROM PUBLIC;
-- Only the functions below touch it.
CREATE POLICY owner_definer_insert ON recap_notifications FOR INSERT TO CURRENT_USER
    WITH CHECK (true);
CREATE POLICY owner_definer_read ON recap_notifications FOR SELECT TO CURRENT_USER USING (true);

-- Games played since `since` in live groups, with the signed-up players in each (guests
-- have no account to notify). The job groups them into outings.
CREATE FUNCTION app_jobs_recent_matches(since timestamptz)
RETURNS TABLE (group_id uuid, group_name text, match_id uuid, played_at timestamptz,
               user_ids uuid[])
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT m.group_id, g.name, m.id, m.played_at,
           coalesce(array_agg(p.user_id) FILTER (WHERE p.user_id IS NOT NULL), '{{}}')
    FROM public.matches m
    JOIN public.groups g ON g.id = m.group_id AND g.deleted_at IS NULL
    JOIN public.match_players mp ON mp.match_id = m.id
    JOIN public.players p ON p.id = mp.player_id
    WHERE m.played_at >= since
    GROUP BY m.group_id, g.name, m.id, m.played_at
$$;

-- True the first time an outing is claimed for its push, false after.
CREATE FUNCTION app_jobs_claim_recap(target_group uuid, key uuid) RETURNS boolean
LANGUAGE sql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    WITH claimed AS (
        INSERT INTO public.recap_notifications (group_id, outing_key)
        VALUES (target_group, key)
        ON CONFLICT DO NOTHING
        RETURNING 1
    )
    SELECT EXISTS (SELECT 1 FROM claimed)
$$;

-- Devices of those players who are still active members and haven't muted recaps.
CREATE FUNCTION app_jobs_recap_targets(target_group uuid, users uuid[])
RETURNS TABLE (endpoint text, p256dh text, auth text)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT s.endpoint, s.p256dh, s.auth
    FROM public.group_members m
    JOIN public.push_subscriptions s ON s.user_id = m.user_id
    LEFT JOIN public.notification_settings ns ON ns.user_id = m.user_id
    WHERE m.group_id = target_group AND m.status = 'active'
      AND m.user_id = ANY(users)
      AND NOT ('recaps' = ANY(coalesce(ns.muted, '{{}}')))
$$;
"""


def upgrade() -> None:
    op.execute(UPGRADE)
    for signature in FUNCTIONS:
        op.execute(f"REVOKE EXECUTE ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO {JOBS_ROLE}")


def downgrade() -> None:
    for signature in FUNCTIONS:
        op.execute(f"DROP FUNCTION {signature}")
    op.execute("DROP TABLE recap_notifications")
    # Development and tests only (see 0014): forget anyone's muted recaps first.
    op.execute(
        "CREATE POLICY downgrade_0016 ON notification_settings FOR UPDATE TO CURRENT_USER "
        "USING (true) WITH CHECK (true)"
    )
    op.execute("UPDATE notification_settings SET muted = array_remove(muted, 'recaps')")
    op.execute("DROP POLICY downgrade_0016 ON notification_settings")
    op.execute(
        "ALTER TABLE notification_settings DROP CONSTRAINT notification_settings_muted_check"
    )
    op.execute(
        "ALTER TABLE notification_settings ADD CONSTRAINT notification_settings_muted_check "
        f"CHECK (muted <@ ARRAY[{OLD_CATEGORIES}]::text[])"
    )
