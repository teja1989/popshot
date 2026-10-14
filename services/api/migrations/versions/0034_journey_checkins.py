"""Journey check-ins: every two weeks, a look at how your game is growing.

Revision ID: 0034
Revises: 0033
Create Date: 2026-10-14

The scheduled job (ops/tick.py) makes a check-in for each person whose journey is on, once
two weeks have passed since their last one (or since they first opened their journey), but
only if they played or reflected on a game in that time: nobody is nudged for taking a break.
It makes the row (the period it covers) and sends "Your check-in is ready"; the API writes
the words when it's opened, from the games and notes of that period (with Gemini, if they've
said yes to that, else Popshot's own lines), and keeps them.

journey_checkins rows are yours alone, like the rest of the journey (0032). Only the job
function adds them, so a period can't be made up; the app may read yours and fill in the
words. They go with a deleted account (app_forget_journey, now covering them too).

journey_settings gains started_at: when you first opened your journey, where the first
period starts. Notifications get a 'journey' category, so the push can be turned off; the
check-in is still made, and shows in the app.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0034"
down_revision: str | None = "0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "popshot_app"
JOBS_ROLE = "popshot_jobs"
JOB_FUNCTIONS = ["app_jobs_claim_journey(timestamptz, interval)"]
PRIVATE_FUNCTIONS = ["app_feature_on_for_user(text, uuid)"]
OLD_CATEGORIES = (
    "'games', 'play_nights', 'tab', 'milestones', 'recaps', 'invites', 'requests', 'your_week'"
)
NEW_CATEGORIES = f"{OLD_CATEGORIES}, 'journey'"
CHAPTERS = "'feet', 'rallies', 'kitchen', 'plan', 'sharpening'"

FORGET = """
CREATE OR REPLACE FUNCTION app_forget_journey() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
    DELETE FROM public.journey_entries j WHERE j.user_id = NEW.id;
    DELETE FROM public.journey_notes j WHERE j.user_id = NEW.id;
    DELETE FROM public.journey_settings j WHERE j.user_id = NEW.id;
    {checkins}
    RETURN NEW;
END;
$$;
"""

UPGRADE = f"""
ALTER TABLE notification_settings DROP CONSTRAINT notification_settings_muted_check;
ALTER TABLE notification_settings ADD CONSTRAINT notification_settings_muted_check
    CHECK (muted <@ ARRAY[{NEW_CATEGORIES}]::text[]);

ALTER TABLE journey_settings ADD COLUMN started_at timestamptz NOT NULL DEFAULT now();

CREATE TABLE journey_checkins (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    period_start timestamptz NOT NULL,
    period_end timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    -- Filled in when it's opened.
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'ready')),
    chapter text CHECK (chapter IN ({CHAPTERS})),
    headline text CHECK (char_length(headline) BETWEEN 1 AND 120),
    lines text[] NOT NULL DEFAULT '{{}}' CHECK (cardinality(lines) <= 6),
    try_next text CHECK (char_length(try_next) BETWEEN 1 AND 200),
    picks uuid[] NOT NULL DEFAULT '{{}}' CHECK (cardinality(picks) <= 3),
    written_by text CHECK (written_by IN ('popshot', 'ai')),
    model text CHECK (char_length(model) <= 80),
    facts_hash text CHECK (char_length(facts_hash) = 64),
    attempts integer NOT NULL DEFAULT 0 CHECK (attempts BETWEEN 0 AND 10),
    written_at timestamptz,
    opened_at timestamptz,
    UNIQUE (user_id, period_start),
    CHECK (period_end > period_start),
    CHECK (status = 'pending' OR (headline IS NOT NULL AND chapter IS NOT NULL
                                  AND written_by IS NOT NULL AND written_at IS NOT NULL))
);
CREATE INDEX journey_checkins_user_idx ON journey_checkins (user_id, period_end DESC);

ALTER TABLE journey_checkins ENABLE ROW LEVEL SECURITY;
ALTER TABLE journey_checkins FORCE ROW LEVEL SECURITY;
REVOKE ALL ON journey_checkins FROM PUBLIC;
-- Yours only. The app reads them and fills in the words; it can't add or remove one.
CREATE POLICY app_own_read ON journey_checkins FOR SELECT TO {APP_ROLE}
    USING (user_id = app_current_user_id());
CREATE POLICY app_own_write ON journey_checkins FOR UPDATE TO {APP_ROLE}
    USING (user_id = app_current_user_id())
    WITH CHECK (user_id = app_current_user_id());
CREATE POLICY owner_definer_read ON journey_checkins FOR SELECT TO CURRENT_USER USING (true);
CREATE POLICY owner_definer_insert ON journey_checkins FOR INSERT TO CURRENT_USER
    WITH CHECK (true);
CREATE POLICY owner_definer_delete ON journey_checkins FOR DELETE TO CURRENT_USER
    USING (true);
GRANT SELECT ON journey_checkins TO {APP_ROLE};
GRANT UPDATE (status, chapter, headline, lines, try_next, picks, written_by, model,
              facts_hash, attempts, written_at, opened_at)
    ON journey_checkins TO {APP_ROLE};

{FORGET.format(checkins="DELETE FROM public.journey_checkins j WHERE j.user_id = NEW.id;")}

-- Is this 'you' switch on for this person (as app_feature_on_for_me, 0032, for anyone)?
-- Private: only the job function below uses it.
CREATE FUNCTION app_feature_on_for_user(feature_key text, target uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT coalesce((
        SELECT CASE
            WHEN f.rollout = 'everyone' AND f.needs_plan IS NULL THEN true
            ELSE EXISTS (
                SELECT 1 FROM public.group_members m
                WHERE m.user_id = target AND m.status = 'active'
                  AND public.app_feature_allowed(f.key, m.group_id))
        END
        FROM public.features f
        WHERE f.key = feature_key AND f.area = 'you'
    ), false)
$$;

-- Makes a check-in for everyone due one at `at`: journey on, `every` since their last
-- check-in (or since they started), and a game played or reflected on in that time. Returns
-- the devices of those who haven't muted 'journey'. Claimed once: a period's start is unique.
CREATE FUNCTION app_jobs_claim_journey(at timestamptz, every interval)
RETURNS TABLE (endpoint text, p256dh text, auth text)
LANGUAGE sql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    WITH periods AS (
        SELECT s.user_id,
               coalesce((SELECT max(c.period_end) FROM public.journey_checkins c
                         WHERE c.user_id = s.user_id), s.started_at) AS since
        FROM public.journey_settings s
        JOIN public.users u ON u.id = s.user_id AND u.deleted_at IS NULL
        WHERE public.app_feature_on_for_user('you.journey', s.user_id)
    ),
    due AS (
        SELECT p.user_id, p.since FROM periods p
        WHERE p.since <= at - every
          AND (EXISTS (
                  SELECT 1 FROM public.players pl
                  JOIN public.match_players mp ON mp.player_id = pl.id
                  JOIN public.matches m ON m.id = mp.match_id
                  WHERE pl.user_id = p.user_id
                    AND m.played_at >= p.since AND m.played_at < at)
               OR EXISTS (
                  SELECT 1 FROM public.match_reflections r
                  WHERE r.user_id = p.user_id
                    AND r.created_at >= p.since AND r.created_at < at
                    AND cardinality(r.went_well) + cardinality(r.to_improve) > 0))
    ),
    claimed AS (
        INSERT INTO public.journey_checkins (user_id, period_start, period_end)
        SELECT due.user_id, due.since, at FROM due
        ON CONFLICT (user_id, period_start) DO NOTHING
        RETURNING user_id
    )
    SELECT s.endpoint, s.p256dh, s.auth
    FROM claimed c
    JOIN public.push_subscriptions s ON s.user_id = c.user_id
    LEFT JOIN public.notification_settings ns ON ns.user_id = c.user_id
    WHERE NOT ('journey' = ANY(coalesce(ns.muted, '{{}}')))
$$;
"""


def upgrade() -> None:
    op.execute(UPGRADE)
    for signature in PRIVATE_FUNCTIONS:
        op.execute(f"REVOKE EXECUTE ON FUNCTION {signature} FROM PUBLIC")
    for signature in JOB_FUNCTIONS:
        op.execute(f"REVOKE EXECUTE ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO {JOBS_ROLE}")


def downgrade() -> None:
    for signature in JOB_FUNCTIONS + PRIVATE_FUNCTIONS:
        op.execute(f"DROP FUNCTION {signature}")
    op.execute(FORGET.format(checkins=""))
    op.execute("DROP TABLE journey_checkins")
    op.execute("ALTER TABLE journey_settings DROP COLUMN started_at")
    # Development and tests only (see 0014): forget anyone's muted 'journey' first.
    op.execute(
        "CREATE POLICY downgrade_0034 ON notification_settings FOR UPDATE TO CURRENT_USER "
        "USING (true) WITH CHECK (true)"
    )
    op.execute("UPDATE notification_settings SET muted = array_remove(muted, 'journey')")
    op.execute("DROP POLICY downgrade_0034 ON notification_settings")
    op.execute(
        "ALTER TABLE notification_settings DROP CONSTRAINT notification_settings_muted_check"
    )
    op.execute(
        "ALTER TABLE notification_settings ADD CONSTRAINT notification_settings_muted_check "
        f"CHECK (muted <@ ARRAY[{OLD_CATEGORIES}]::text[])"
    )
