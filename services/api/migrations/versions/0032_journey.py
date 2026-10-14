"""Your pickleball journey: your story in your own words, learning notes, and per-person switches.

Revision ID: 0032
Revises: 0031
Create Date: 2026-10-14

journey_entries is your story: how you got into pickleball, what you're good at, what lets
you down, and a goal. Each save adds a new dated version and never changes an old one (the
app role may only read and add), so a check-in can say what changed since last time. Each
version carries skill tags from the focus list (0003): yours, copied from your focus, or (from
a later step) read from your words by the AI. Who chose them is kept in tags_source.

journey_notes are one-line "what did I learn today" notes. You can delete your own.

journey_settings holds whether the AI may read your story (off until you say yes) and whether
you've been asked for your story after signing up.

All three are yours alone, like user_focus: not on users, which crewmates can read. A deleted
account's rows go with it (a trigger, as in 0024 and 0026).

Feature switches (0027) are per crew. The journey is personal, so switches in the 'you' area
are now asked about per person: app_feature_on_for_me is on when the rollout is 'everyone'
(and needs no plan), or when any crew you're active in has it. It works for someone with no
crew. Both new switches start on the beta list ('crews'), so nobody sees the journey until an
admin lists a crew or opens it to everyone.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0032"
down_revision: str | None = "0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "popshot_app"
APP_FUNCTIONS = ["app_feature_on_for_me(text)", "app_my_personal_features()"]
TABLES = ["journey_entries", "journey_notes", "journey_settings"]

UPGRADE = f"""
CREATE TABLE journey_entries (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now(),
    -- In your own words, each optional; at least one is filled in.
    origin text NOT NULL DEFAULT '' CHECK (char_length(origin) <= 800),
    strengths text NOT NULL DEFAULT '' CHECK (char_length(strengths) <= 500),
    gaps text NOT NULL DEFAULT '' CHECK (char_length(gaps) <= 500),
    goal text NOT NULL DEFAULT '' CHECK (char_length(goal) <= 300),
    -- Skills from the focus list, as read from the words above.
    tag_strengths text[] NOT NULL DEFAULT '{{}}'
        CHECK (cardinality(tag_strengths) <= 4 AND app_valid_focus_ids(tag_strengths)),
    tag_gaps text[] NOT NULL DEFAULT '{{}}'
        CHECK (cardinality(tag_gaps) <= 4 AND app_valid_focus_ids(tag_gaps)),
    tags_source text NOT NULL CHECK (tags_source IN ('player', 'rules', 'ai')),
    CHECK (btrim(origin || strengths || gaps || goal) <> ''),
    CHECK (NOT (tag_strengths && tag_gaps))
);
CREATE INDEX journey_entries_user_idx ON journey_entries (user_id, created_at DESC);

CREATE TABLE journey_notes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    noted_on date NOT NULL DEFAULT current_date,
    body text NOT NULL CHECK (char_length(btrim(body)) BETWEEN 1 AND 200),
    -- Optionally, the skill it's about.
    skill text CHECK (skill ~ '^[a-z][a-z0-9_]{{0,39}}$'),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX journey_notes_user_idx ON journey_notes (user_id, created_at DESC);

CREATE TABLE journey_settings (
    user_id uuid PRIMARY KEY REFERENCES users (id) ON DELETE CASCADE,
    ai_consent boolean NOT NULL DEFAULT false,
    -- After signing up: not asked yet, skipped, or done.
    onboarding text NOT NULL DEFAULT 'new' CHECK (onboarding IN ('new', 'skipped', 'done')),
    updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE journey_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE journey_entries FORCE ROW LEVEL SECURITY;
ALTER TABLE journey_notes ENABLE ROW LEVEL SECURITY;
ALTER TABLE journey_notes FORCE ROW LEVEL SECURITY;
ALTER TABLE journey_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE journey_settings FORCE ROW LEVEL SECURITY;
REVOKE ALL ON journey_entries, journey_notes, journey_settings FROM PUBLIC;

-- Yours only.
CREATE POLICY app_own ON journey_entries FOR ALL TO {APP_ROLE}
    USING (user_id = app_current_user_id())
    WITH CHECK (user_id = app_current_user_id());
CREATE POLICY app_own ON journey_notes FOR ALL TO {APP_ROLE}
    USING (user_id = app_current_user_id())
    WITH CHECK (user_id = app_current_user_id());
CREATE POLICY app_own ON journey_settings FOR ALL TO {APP_ROLE}
    USING (user_id = app_current_user_id())
    WITH CHECK (user_id = app_current_user_id());
-- For the clean-up when an account is deleted (a DELETE with a WHERE needs to read, too).
CREATE POLICY owner_definer_read ON journey_entries FOR SELECT TO CURRENT_USER USING (true);
CREATE POLICY owner_definer_read ON journey_notes FOR SELECT TO CURRENT_USER USING (true);
CREATE POLICY owner_definer_read ON journey_settings FOR SELECT TO CURRENT_USER USING (true);
CREATE POLICY owner_definer_delete ON journey_entries FOR DELETE TO CURRENT_USER USING (true);
CREATE POLICY owner_definer_delete ON journey_notes FOR DELETE TO CURRENT_USER USING (true);
CREATE POLICY owner_definer_delete ON journey_settings FOR DELETE TO CURRENT_USER USING (true);

-- Versions are only ever added; notes can be added or deleted, not edited.
GRANT SELECT, INSERT ON journey_entries TO {APP_ROLE};
GRANT SELECT, INSERT, DELETE ON journey_notes TO {APP_ROLE};
GRANT SELECT, INSERT, UPDATE (ai_consent, onboarding, updated_at) ON journey_settings
    TO {APP_ROLE};

-- A deleted account's journey goes with it.
CREATE FUNCTION app_forget_journey() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
    DELETE FROM public.journey_entries j WHERE j.user_id = NEW.id;
    DELETE FROM public.journey_notes j WHERE j.user_id = NEW.id;
    DELETE FROM public.journey_settings j WHERE j.user_id = NEW.id;
    RETURN NEW;
END;
$$;
REVOKE EXECUTE ON FUNCTION app_forget_journey() FROM PUBLIC;
CREATE TRIGGER users_forget_journey
    AFTER UPDATE OF deleted_at ON users
    FOR EACH ROW WHEN (NEW.deleted_at IS NOT NULL AND OLD.deleted_at IS NULL)
    EXECUTE FUNCTION app_forget_journey();

-- Is this 'you' switch on for the signed-in person? Switches in other areas are per crew
-- (app_feature_on), so they're always false here.
CREATE FUNCTION app_feature_on_for_me(feature_key text) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT coalesce((
        SELECT CASE
            WHEN public.app_current_user_id() IS NULL THEN false
            WHEN f.rollout = 'everyone' AND f.needs_plan IS NULL THEN true
            ELSE EXISTS (
                SELECT 1 FROM public.group_members m
                WHERE m.user_id = public.app_current_user_id() AND m.status = 'active'
                  AND public.app_feature_allowed(f.key, m.group_id))
        END
        FROM public.features f
        WHERE f.key = feature_key AND f.area = 'you'
    ), false)
$$;

-- Every 'you' switch that's on for the signed-in person.
CREATE FUNCTION app_my_personal_features() RETURNS TABLE (feature text)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT f.key FROM public.features f
    WHERE f.area = 'you' AND public.app_feature_on_for_me(f.key)
    ORDER BY f.key
$$;

INSERT INTO features (key, area, title, description, needs_plan, rollout) VALUES
    ('you.journey', 'you', 'Your journey',
     'Your pickleball story, learning notes and check-ins, on the Journey tab of You.',
     NULL, 'crews'),
    ('you.journey_ai', 'you', 'AI on your journey',
     'Gemini reads your story, if you allow it, to tag skills and write check-ins. Off: rules.',
     NULL, 'crews');
"""


def upgrade() -> None:
    op.execute(UPGRADE)
    for signature in APP_FUNCTIONS:
        op.execute(f"REVOKE EXECUTE ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO {APP_ROLE}")


def downgrade() -> None:
    op.execute("DELETE FROM features WHERE key IN ('you.journey', 'you.journey_ai')")
    for signature in APP_FUNCTIONS:
        op.execute(f"DROP FUNCTION {signature}")
    op.execute("DROP TRIGGER users_forget_journey ON users")
    op.execute("DROP FUNCTION app_forget_journey()")
    for table in TABLES:
        op.execute(f"DROP TABLE {table}")
