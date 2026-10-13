"""Feature switches and crew plans: what's on, for which crews, changed by an admin at once.

Revision ID: 0027
Revises: 0026
Create Date: 2026-10-13

features lists what can be switched. Each has a rollout:
- 'off': nobody has it. The kill switch: it beats every list and plan.
- 'crews': only the crews in feature_crews (a beta list an admin keeps).
- 'everyone': every crew if it's free; if it needs a plan (needs_plan), only crews with
  that plan running now in crew_plans.
crew_plans is what a crew has: 'organizer' for now, from 'beta', 'comp' or (later, from
payments) 'subscription', with an optional end.

app_feature_allowed holds that rule, once. It isn't granted to anyone: the functions that use
it are. app_feature_on and app_my_features answer for a crew you're an active member of, so
nobody can probe another crew's plan; app_share_feature_on answers for the crew behind a
live share link. Every check reads these tables inside the caller's transaction (no cache),
so an admin's change applies to the very next request, with no deploy or restart.

Only the admin service (popshot_admin) changes them, through the functions below, which log
each change in admin_actions (0013) with what it was before and after, and a reason.

A feature's row arrives in the migration that builds it. This one adds recaps.ai (the AI
recap writer), on for everyone, so nothing changes until an admin turns it off.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0027"
down_revision: str | None = "0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "popshot_app"
ADMIN_ROLE = "popshot_admin"
APP_FUNCTIONS = [
    "app_feature_on(text, uuid)",
    "app_my_features()",
    "app_share_feature_on(bytea, text)",
]
ADMIN_FUNCTIONS = [
    "app_admin_features()",
    "app_admin_feature_crews(text)",
    "app_admin_crew_plan(uuid)",
    "app_admin_crew_features(uuid)",
    "app_admin_plans()",
    "app_admin_set_feature_rollout(text, text, text)",
    "app_admin_set_feature_plan(text, text, text)",
    "app_admin_add_feature_crew(text, uuid, text)",
    "app_admin_remove_feature_crew(text, uuid, text)",
    "app_admin_grant_plan(uuid, text, text, timestamptz, text, text)",
    "app_admin_end_plan(uuid, text, text)",
]
PRIVATE_FUNCTIONS = ["app_feature_allowed(text, uuid)"]

UPGRADE = """
CREATE TABLE features (
    key text PRIMARY KEY CHECK (key ~ '^[a-z][a-z0-9_]*(\\.[a-z][a-z0-9_]*)+$'
                                AND char_length(key) <= 64),
    -- Where it lives: the admin page's tabs and the app's menu group by this.
    area text NOT NULL CHECK (area IN ('events', 'learn', 'recaps', 'courts', 'crew', 'play',
                                       'home', 'you')),
    title text NOT NULL CHECK (char_length(title) BETWEEN 1 AND 60),
    description text NOT NULL CHECK (char_length(description) BETWEEN 1 AND 300),
    needs_plan text CHECK (needs_plan IN ('organizer')),
    rollout text NOT NULL DEFAULT 'off' CHECK (rollout IN ('off', 'crews', 'everyone')),
    updated_by uuid REFERENCES users (id) ON DELETE SET NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE feature_crews (
    feature_key text NOT NULL REFERENCES features (key) ON DELETE CASCADE,
    group_id uuid NOT NULL REFERENCES groups (id) ON DELETE CASCADE,
    added_by uuid REFERENCES users (id) ON DELETE SET NULL,
    added_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (feature_key, group_id)
);

CREATE TABLE crew_plans (
    group_id uuid NOT NULL REFERENCES groups (id) ON DELETE CASCADE,
    plan text NOT NULL CHECK (plan IN ('organizer')),
    source text NOT NULL CHECK (source IN ('beta', 'comp', 'subscription')),
    starts_at timestamptz NOT NULL DEFAULT now(),
    ends_at timestamptz CHECK (ends_at IS NULL OR ends_at > starts_at),
    note text CHECK (char_length(note) <= 200),
    granted_by uuid REFERENCES users (id) ON DELETE SET NULL,
    granted_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (group_id, plan)
);

ALTER TABLE features ENABLE ROW LEVEL SECURITY;
ALTER TABLE features FORCE ROW LEVEL SECURITY;
ALTER TABLE feature_crews ENABLE ROW LEVEL SECURITY;
ALTER TABLE feature_crews FORCE ROW LEVEL SECURITY;
ALTER TABLE crew_plans ENABLE ROW LEVEL SECURITY;
ALTER TABLE crew_plans FORCE ROW LEVEL SECURITY;
REVOKE ALL ON features, feature_crews, crew_plans FROM PUBLIC;
-- No role reads or writes them directly: only the functions below (and migrations).
CREATE POLICY owner_definer_all ON features FOR ALL TO CURRENT_USER
    USING (true) WITH CHECK (true);
CREATE POLICY owner_definer_all ON feature_crews FOR ALL TO CURRENT_USER
    USING (true) WITH CHECK (true);
CREATE POLICY owner_definer_all ON crew_plans FOR ALL TO CURRENT_USER
    USING (true) WITH CHECK (true);

-- The rule, for any crew. Not granted to anyone: only the functions below call it.
CREATE FUNCTION app_feature_allowed(feature_key text, target_group uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT coalesce((
        SELECT CASE f.rollout
            WHEN 'crews' THEN EXISTS (
                SELECT 1 FROM public.feature_crews c
                WHERE c.feature_key = f.key AND c.group_id = target_group)
            WHEN 'everyone' THEN f.needs_plan IS NULL OR EXISTS (
                SELECT 1 FROM public.crew_plans p
                WHERE p.group_id = target_group AND p.plan = f.needs_plan
                  AND p.starts_at <= now() AND (p.ends_at IS NULL OR p.ends_at > now()))
            ELSE false
        END
        FROM public.features f
        JOIN public.groups g ON g.id = target_group AND g.deleted_at IS NULL
        WHERE f.key = feature_key
    ), false)
$$;

-- Is this feature on for a crew you're an active member of? False for anyone else.
CREATE FUNCTION app_feature_on(feature_key text, target_group uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT EXISTS (
        SELECT 1 FROM public.group_members m
        WHERE m.group_id = target_group
          AND m.user_id = public.app_current_user_id()
          AND m.status = 'active'
    ) AND public.app_feature_allowed(feature_key, target_group)
$$;

-- Everything that's on, for each crew you're an active member of.
CREATE FUNCTION app_my_features() RETURNS TABLE (group_id uuid, feature text)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT m.group_id, f.key
    FROM public.group_members m
    CROSS JOIN public.features f
    WHERE m.user_id = public.app_current_user_id()
      AND m.status = 'active'
      AND public.app_feature_allowed(f.key, m.group_id)
    ORDER BY m.group_id, f.key
$$;

-- For the crew behind a live share link (0017), for public pages with no one signed in.
CREATE FUNCTION app_share_feature_on(token bytea, feature_key text) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT coalesce((
        SELECT public.app_feature_allowed(feature_key, s.group_id)
        FROM public.app_public_share(token) s
    ), false)
$$;

-- Admin: every feature, with how many crews are on its list and who changed it last.
CREATE FUNCTION app_admin_features()
RETURNS TABLE (key text, area text, title text, description text, needs_plan text,
               rollout text, crews integer, updated_at timestamptz, updated_by_name text)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT f.key, f.area, f.title, f.description, f.needs_plan, f.rollout,
        (SELECT count(*)::integer FROM public.feature_crews c
         JOIN public.groups g ON g.id = c.group_id AND g.deleted_at IS NULL
         WHERE c.feature_key = f.key),
        f.updated_at, u.display_name
    FROM public.features f
    LEFT JOIN public.users u ON u.id = f.updated_by
    ORDER BY f.area, f.key
$$;

CREATE FUNCTION app_admin_feature_crews(feature_key text)
RETURNS TABLE (group_id uuid, name text, added_at timestamptz, added_by_name text)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT c.group_id, g.name, c.added_at, u.display_name
    FROM public.feature_crews c
    JOIN public.groups g ON g.id = c.group_id AND g.deleted_at IS NULL
    LEFT JOIN public.users u ON u.id = c.added_by
    WHERE c.feature_key = app_admin_feature_crews.feature_key
    ORDER BY g.name, c.group_id
$$;

CREATE FUNCTION app_admin_crew_plan(target_group uuid)
RETURNS TABLE (plan text, source text, starts_at timestamptz, ends_at timestamptz,
               note text, granted_at timestamptz, granted_by_name text)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT p.plan, p.source, p.starts_at, p.ends_at, p.note, p.granted_at, u.display_name
    FROM public.crew_plans p
    LEFT JOIN public.users u ON u.id = p.granted_by
    WHERE p.group_id = target_group
    ORDER BY p.plan
$$;

-- Which features are on for a crew right now (whoever is asking).
CREATE FUNCTION app_admin_crew_features(target_group uuid) RETURNS TABLE (feature text)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT f.key FROM public.features f
    WHERE public.app_feature_allowed(f.key, target_group)
    ORDER BY f.key
$$;

-- Every crew with a plan, running or ended, newest first.
CREATE FUNCTION app_admin_plans()
RETURNS TABLE (group_id uuid, name text, plan text, source text, starts_at timestamptz,
               ends_at timestamptz, note text)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT p.group_id, g.name, p.plan, p.source, p.starts_at, p.ends_at, p.note
    FROM public.crew_plans p
    JOIN public.groups g ON g.id = p.group_id AND g.deleted_at IS NULL
    ORDER BY p.granted_at DESC
    LIMIT 500
$$;

-- The changes. Each returns an outcome: 'done', or why not. Each 'done' is logged with the
-- reason and what it was before and after, in the same transaction.

CREATE FUNCTION app_admin_set_feature_rollout(feature_key text, new_rollout text, why text)
RETURNS text
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    me uuid := public.app_current_user_id();
    before text;
BEGIN
    IF me IS NULL THEN
        RAISE EXCEPTION 'no signed-in user' USING ERRCODE = 'insufficient_privilege';
    END IF;
    SELECT f.rollout INTO before FROM public.features f WHERE f.key = feature_key FOR UPDATE;
    IF NOT FOUND THEN
        RETURN 'no_feature';
    END IF;
    IF before = new_rollout THEN
        RETURN 'unchanged';
    END IF;
    UPDATE public.features f SET rollout = new_rollout, updated_by = me, updated_at = now()
    WHERE f.key = feature_key;
    INSERT INTO public.admin_actions (admin_user_id, action, reason, details)
    VALUES (me, 'feature.rollout', btrim(why), jsonb_build_object(
        'feature', feature_key, 'before', before, 'after', new_rollout));
    RETURN 'done';
END;
$$;

CREATE FUNCTION app_admin_set_feature_plan(feature_key text, new_plan text, why text)
RETURNS text
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    me uuid := public.app_current_user_id();
    before text;
BEGIN
    IF me IS NULL THEN
        RAISE EXCEPTION 'no signed-in user' USING ERRCODE = 'insufficient_privilege';
    END IF;
    PERFORM 1 FROM public.features f WHERE f.key = feature_key FOR UPDATE;
    IF NOT FOUND THEN
        RETURN 'no_feature';
    END IF;
    SELECT f.needs_plan INTO before FROM public.features f WHERE f.key = feature_key;
    IF before IS NOT DISTINCT FROM new_plan THEN
        RETURN 'unchanged';
    END IF;
    UPDATE public.features f SET needs_plan = new_plan, updated_by = me, updated_at = now()
    WHERE f.key = feature_key;
    INSERT INTO public.admin_actions (admin_user_id, action, reason, details)
    VALUES (me, 'feature.plan', btrim(why), jsonb_build_object(
        'feature', feature_key, 'before', before, 'after', new_plan));
    RETURN 'done';
END;
$$;

CREATE FUNCTION app_admin_add_feature_crew(feature_key text, target_group uuid, why text)
RETURNS text
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    me uuid := public.app_current_user_id();
BEGIN
    IF me IS NULL THEN
        RAISE EXCEPTION 'no signed-in user' USING ERRCODE = 'insufficient_privilege';
    END IF;
    PERFORM 1 FROM public.features f WHERE f.key = feature_key;
    IF NOT FOUND THEN
        RETURN 'no_feature';
    END IF;
    PERFORM 1 FROM public.groups g WHERE g.id = target_group AND g.deleted_at IS NULL;
    IF NOT FOUND THEN
        RETURN 'no_crew';
    END IF;
    INSERT INTO public.feature_crews (feature_key, group_id, added_by)
    VALUES (feature_key, target_group, me)
    ON CONFLICT DO NOTHING;
    IF NOT FOUND THEN
        RETURN 'unchanged';
    END IF;
    INSERT INTO public.admin_actions (admin_user_id, action, group_id, reason, details)
    VALUES (me, 'feature.crew_add', target_group, btrim(why), jsonb_build_object(
        'feature', feature_key, 'before', false, 'after', true));
    RETURN 'done';
END;
$$;

CREATE FUNCTION app_admin_remove_feature_crew(feature_key text, target_group uuid, why text)
RETURNS text
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    me uuid := public.app_current_user_id();
BEGIN
    IF me IS NULL THEN
        RAISE EXCEPTION 'no signed-in user' USING ERRCODE = 'insufficient_privilege';
    END IF;
    DELETE FROM public.feature_crews c
    WHERE c.feature_key = app_admin_remove_feature_crew.feature_key
      AND c.group_id = target_group;
    IF NOT FOUND THEN
        RETURN 'unchanged';
    END IF;
    INSERT INTO public.admin_actions (admin_user_id, action, group_id, reason, details)
    VALUES (me, 'feature.crew_remove', target_group, btrim(why), jsonb_build_object(
        'feature', feature_key, 'before', true, 'after', false));
    RETURN 'done';
END;
$$;

-- Give a crew a plan, or change the one it has (source, end, note). A plan that had ended
-- starts again now. 'bad_end' if the end isn't in the future.
CREATE FUNCTION app_admin_grant_plan(target_group uuid, new_plan text, new_source text,
                                     new_ends_at timestamptz, new_note text, why text)
RETURNS text
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    me uuid := public.app_current_user_id();
    old public.crew_plans;
    starts timestamptz := now();
BEGIN
    IF me IS NULL THEN
        RAISE EXCEPTION 'no signed-in user' USING ERRCODE = 'insufficient_privilege';
    END IF;
    PERFORM 1 FROM public.groups g
    WHERE g.id = target_group AND g.deleted_at IS NULL FOR UPDATE;
    IF NOT FOUND THEN
        RETURN 'no_crew';
    END IF;
    IF new_ends_at IS NOT NULL AND new_ends_at <= now() THEN
        RETURN 'bad_end';
    END IF;
    SELECT * INTO old FROM public.crew_plans p
    WHERE p.group_id = target_group AND p.plan = new_plan;
    IF FOUND AND (old.ends_at IS NULL OR old.ends_at > now()) THEN
        starts := old.starts_at;
    END IF;
    INSERT INTO public.crew_plans
        (group_id, plan, source, starts_at, ends_at, note, granted_by, granted_at)
    VALUES (target_group, new_plan, new_source, starts, new_ends_at, nullif(btrim(new_note), ''),
            me, now())
    ON CONFLICT (group_id, plan) DO UPDATE SET
        source = excluded.source, starts_at = excluded.starts_at, ends_at = excluded.ends_at,
        note = excluded.note, granted_by = excluded.granted_by, granted_at = excluded.granted_at;
    INSERT INTO public.admin_actions (admin_user_id, action, group_id, reason, details)
    VALUES (me, 'plan.grant', target_group, btrim(why), jsonb_build_object(
        'plan', new_plan,
        'before', CASE WHEN old.group_id IS NULL THEN NULL ELSE jsonb_build_object(
            'source', old.source, 'starts_at', old.starts_at, 'ends_at', old.ends_at) END,
        'after', jsonb_build_object(
            'source', new_source, 'starts_at', starts, 'ends_at', new_ends_at)));
    RETURN 'done';
END;
$$;

-- End a crew's running plan now. The row stays, as a record.
CREATE FUNCTION app_admin_end_plan(target_group uuid, old_plan text, why text) RETURNS text
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    me uuid := public.app_current_user_id();
    old public.crew_plans;
BEGIN
    IF me IS NULL THEN
        RAISE EXCEPTION 'no signed-in user' USING ERRCODE = 'insufficient_privilege';
    END IF;
    SELECT * INTO old FROM public.crew_plans p
    WHERE p.group_id = target_group AND p.plan = old_plan
      AND (p.ends_at IS NULL OR p.ends_at > now())
    FOR UPDATE;
    IF NOT FOUND THEN
        RETURN 'no_plan';
    END IF;
    -- A plan that hasn't started yet is ended as it starts, so the row stays valid.
    UPDATE public.crew_plans p SET ends_at = greatest(now(), p.starts_at + interval '1 microsecond')
    WHERE p.group_id = target_group AND p.plan = old_plan;
    INSERT INTO public.admin_actions (admin_user_id, action, group_id, reason, details)
    VALUES (me, 'plan.end', target_group, btrim(why), jsonb_build_object(
        'plan', old_plan,
        'before', jsonb_build_object('source', old.source, 'ends_at', old.ends_at),
        'after', jsonb_build_object('ends_at', now())));
    RETURN 'done';
END;
$$;

INSERT INTO features (key, area, title, description, needs_plan, rollout) VALUES
    ('recaps.ai', 'recaps', 'AI recap writing',
     'Recaps written by Gemini. Off: everyone gets the built-in lines instead.',
     NULL, 'everyone');
"""


def upgrade() -> None:
    op.execute(UPGRADE)
    for signature in PRIVATE_FUNCTIONS:
        op.execute(f"REVOKE EXECUTE ON FUNCTION {signature} FROM PUBLIC")
    for signature in APP_FUNCTIONS:
        op.execute(f"REVOKE EXECUTE ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO {APP_ROLE}")
    for signature in ADMIN_FUNCTIONS:
        op.execute(f"REVOKE EXECUTE ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO {ADMIN_ROLE}")


def downgrade() -> None:
    for signature in ADMIN_FUNCTIONS + APP_FUNCTIONS + PRIVATE_FUNCTIONS:
        op.execute(f"DROP FUNCTION {signature}")
    op.execute("DROP TABLE crew_plans")
    op.execute("DROP TABLE feature_crews")
    op.execute("DROP TABLE features")
