"""What the scheduled job (popshot_api.ops.tick) may do, and nothing more.

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-11

The job logs in as its own user, a member of popshot_jobs (created by the bootstrap). That
role has no table privileges at all: it can only run the SECURITY DEFINER functions below,
each of which does one narrow thing. The API's role can't run them, so no request can
trigger a reminder or a purge.

Reminders: the day before a night, and two hours before. play_nights records when each was
sent, so a run that's late catches up, a night is never reminded twice, and nothing is sent
once a night has started.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JOBS_ROLE = "popshot_jobs"
FUNCTIONS = [
    "app_jobs_due_reminders(text)",
    "app_jobs_reminder_targets(uuid, text)",
    "app_jobs_mark_reminded(uuid, text)",
    "app_purge_deleted_groups()",
    "app_forget_push_endpoint(text)",
]

UPGRADE = """
ALTER TABLE play_nights ADD COLUMN reminded_day_at timestamptz,
                        ADD COLUMN reminded_soon_at timestamptz;
-- Moving a night to a new time sets its reminders up again (routes/nights.py).
GRANT UPDATE (reminded_day_at, reminded_soon_at) ON play_nights TO popshot_app;
CREATE INDEX play_nights_due_idx ON play_nights (starts_at)
    WHERE cancelled_at IS NULL AND (reminded_day_at IS NULL OR reminded_soon_at IS NULL);

-- For the functions below: they read and update nights, read who answered what, members
-- and push subscriptions (push_subscriptions already has an owner policy from 0006).
CREATE POLICY owner_definer_read ON play_nights FOR SELECT TO CURRENT_USER USING (true);
CREATE POLICY owner_definer_update ON play_nights FOR UPDATE TO CURRENT_USER
    USING (true) WITH CHECK (true);
CREATE POLICY owner_definer_read ON play_night_rsvps FOR SELECT TO CURRENT_USER USING (true);

-- Nights whose reminder of this kind is due: 'day' within 24 hours of the start, 'soon'
-- within 2 hours. Not cancelled, not started, not already reminded, in a live group.
CREATE FUNCTION app_jobs_due_reminders(kind text)
RETURNS TABLE (night_id uuid, group_id uuid, venue text, starts_at timestamptz)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT n.id, n.group_id, n.venue, n.starts_at
    FROM public.play_nights n
    JOIN public.groups g ON g.id = n.group_id AND g.deleted_at IS NULL
    WHERE n.cancelled_at IS NULL
      AND n.starts_at > now()
      AND CASE kind
            WHEN 'day' THEN n.reminded_day_at IS NULL
                            AND n.starts_at <= now() + interval '24 hours'
            WHEN 'soon' THEN n.reminded_soon_at IS NULL
                             AND n.starts_at <= now() + interval '2 hours'
          END
    ORDER BY n.starts_at
$$;

-- Devices to remind, and who they belong to's answer: 'day' goes to everyone going (in) and
-- to active members who haven't answered; 'soon' only to those who said in. Respects the
-- play_nights category being muted.
CREATE FUNCTION app_jobs_reminder_targets(night uuid, kind text)
RETURNS TABLE (endpoint text, p256dh text, auth text, answered boolean)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT s.endpoint, s.p256dh, s.auth, r.answer IS NOT NULL
    FROM public.play_nights n
    JOIN public.group_members m ON m.group_id = n.group_id AND m.status = 'active'
    LEFT JOIN public.play_night_rsvps r ON r.night_id = n.id AND r.user_id = m.user_id
    JOIN public.push_subscriptions s ON s.user_id = m.user_id
    LEFT JOIN public.notification_settings ns ON ns.user_id = m.user_id
    WHERE n.id = night
      AND NOT ('play_nights' = ANY(coalesce(ns.muted, '{}')))
      AND CASE kind
            WHEN 'day' THEN r.answer = 'in' OR r.answer IS NULL
            WHEN 'soon' THEN r.answer = 'in'
          END
$$;

CREATE FUNCTION app_jobs_mark_reminded(night uuid, kind text) RETURNS void
LANGUAGE sql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    UPDATE public.play_nights SET
        reminded_day_at = CASE WHEN kind = 'day' THEN now() ELSE reminded_day_at END,
        reminded_soon_at = CASE WHEN kind = 'soon' THEN now() ELSE reminded_soon_at END
    WHERE id = night
$$;
"""


def upgrade() -> None:
    op.execute(UPGRADE)
    for signature in FUNCTIONS[:3]:
        op.execute(f"REVOKE EXECUTE ON FUNCTION {signature} FROM PUBLIC")
    for signature in FUNCTIONS:
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO {JOBS_ROLE}")


def downgrade() -> None:
    for signature in FUNCTIONS[3:]:
        op.execute(f"REVOKE EXECUTE ON FUNCTION {signature} FROM {JOBS_ROLE}")
    for signature in FUNCTIONS[:3]:
        op.execute(f"DROP FUNCTION {signature}")
    op.execute("DROP POLICY owner_definer_read ON play_night_rsvps")
    op.execute("DROP POLICY owner_definer_update ON play_nights")
    op.execute("DROP POLICY owner_definer_read ON play_nights")
    op.execute("DROP INDEX play_nights_due_idx")
    op.execute("REVOKE UPDATE (reminded_day_at, reminded_soon_at) ON play_nights FROM popshot_app")
    op.execute("ALTER TABLE play_nights DROP COLUMN reminded_soon_at, DROP COLUMN reminded_day_at")
