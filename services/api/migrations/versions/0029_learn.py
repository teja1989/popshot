"""Learn: shots, each a 3D scene with tips and a drill, written by admins and read by anyone.

Revision ID: 0029
Revises: 0028
Create Date: 2026-10-14

A shot has a working copy, which admins edit, and a published copy, which is what everyone
sees. Publishing copies the working copy across whole, so edits stay private until they're
published again. version goes up with every save; publishing names the version it checked,
and is refused if the shot changed since. A published shot's slug is its address, so it
can't change once the shot has been published.

Nobody reads or writes shots directly:
- Anyone, signed in or not: app_public_shots and app_public_shot, which return published
  copies only, and nothing at all unless the 'learn.public' switch (0027) is on for everyone.
  It's off here, so nothing shows until an admin turns it on.
- The admin service (popshot_admin): the functions below. Creating, publishing, unpublishing
  and deleting are logged in admin_actions (0013) with a reason. Saves to the working copy
  aren't: nobody else sees them, and each one records who and when.

The API checks a scene's shape (popshot_api.learn.scene) before it gets here; this keeps
each piece within bounds as well.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0029"
down_revision: str | None = "0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "popshot_app"
ADMIN_ROLE = "popshot_admin"
APP_FUNCTIONS = ["app_public_shots()", "app_public_shot(text)"]
ADMIN_FUNCTIONS = [
    "app_admin_shots()",
    "app_admin_shot(uuid)",
    "app_admin_create_shot(text, text, text, text, text[], text[], text[], jsonb, text)",
    "app_admin_save_shot(uuid, integer, text, text, text, text, text[], text[], text[], jsonb)",
    "app_admin_publish_shot(uuid, integer, text)",
    "app_admin_unpublish_shot(uuid, text)",
    "app_admin_delete_shot(uuid, text)",
]
PRIVATE_FUNCTIONS = ["app_learn_public()"]

UPGRADE = """
CREATE TABLE shots (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug text NOT NULL UNIQUE CHECK (slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'
                                     AND char_length(slug) <= 60),
    title text NOT NULL CHECK (char_length(btrim(title)) BETWEEN 1 AND 60),
    summary text NOT NULL CHECK (char_length(btrim(summary)) BETWEEN 1 AND 200),
    level text NOT NULL CHECK (level IN ('beginner', 'intermediate', 'advanced', 'expert')),
    -- Ids from popshot_api.focus, so a shot meets the focus areas players already pick.
    focus_ids text[] NOT NULL CHECK (cardinality(focus_ids) BETWEEN 1 AND 4
                                     AND array_position(focus_ids, NULL) IS NULL
                                     AND array_to_string(focus_ids, ',') ~ '^[a-z_,]+$'),
    tips text[] NOT NULL CHECK (cardinality(tips) <= 8
                                AND array_position(tips, NULL) IS NULL
                                AND char_length(array_to_string(tips, '')) <= 8 * 200),
    drill_steps text[] NOT NULL CHECK (cardinality(drill_steps) <= 10
                                       AND array_position(drill_steps, NULL) IS NULL
                                       AND char_length(array_to_string(drill_steps, ''))
                                           <= 10 * 200),
    scene jsonb NOT NULL CHECK (jsonb_typeof(scene) = 'object'
                                AND octet_length(scene::text) <= 32768),
    version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
    -- What everyone sees: the working copy as it was at published_version.
    published jsonb CHECK (published IS NULL OR (jsonb_typeof(published) = 'object'
                                                  AND octet_length(published::text) <= 49152)),
    published_version integer,
    published_at timestamptz,
    first_published_at timestamptz,
    created_by uuid REFERENCES users (id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_by uuid REFERENCES users (id) ON DELETE SET NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK ((published IS NULL) = (published_version IS NULL)
           AND (published IS NULL) = (published_at IS NULL)),
    CHECK (published IS NULL OR first_published_at IS NOT NULL)
);

ALTER TABLE shots ENABLE ROW LEVEL SECURITY;
ALTER TABLE shots FORCE ROW LEVEL SECURITY;
REVOKE ALL ON shots FROM PUBLIC;
CREATE POLICY owner_definer_all ON shots FOR ALL TO CURRENT_USER
    USING (true) WITH CHECK (true);

-- Is Learn open to the public? Only an 'everyone' rollout counts: it isn't per crew.
CREATE FUNCTION app_learn_public() RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT EXISTS (
        SELECT 1 FROM public.features f WHERE f.key = 'learn.public' AND f.rollout = 'everyone')
$$;

CREATE FUNCTION app_public_shots()
RETURNS TABLE (slug text, title text, summary text, level text, focus_ids text[],
               published_at timestamptz)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT s.slug, s.published->>'title', s.published->>'summary', s.published->>'level',
        ARRAY(SELECT jsonb_array_elements_text(s.published->'focus_ids')), s.published_at
    FROM public.shots s
    WHERE s.published IS NOT NULL AND public.app_learn_public()
    ORDER BY s.published->>'title', s.slug
$$;

CREATE FUNCTION app_public_shot(shot_slug text)
RETURNS TABLE (slug text, shot jsonb, published_at timestamptz)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT s.slug, s.published, s.published_at
    FROM public.shots s
    WHERE s.slug = shot_slug AND s.published IS NOT NULL AND public.app_learn_public()
$$;

CREATE FUNCTION app_admin_shots()
RETURNS TABLE (id uuid, slug text, title text, level text, focus_ids text[], version integer,
               updated_at timestamptz, updated_by_name text, published_version integer,
               published_at timestamptz)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT s.id, s.slug, s.title, s.level, s.focus_ids, s.version, s.updated_at,
        u.display_name, s.published_version, s.published_at
    FROM public.shots s
    LEFT JOIN public.users u ON u.id = s.updated_by
    ORDER BY s.title, s.slug
$$;

CREATE FUNCTION app_admin_shot(shot_id uuid)
RETURNS TABLE (id uuid, slug text, title text, summary text, level text, focus_ids text[],
               tips text[], drill_steps text[], scene jsonb, version integer,
               updated_at timestamptz, updated_by_name text, published_version integer,
               published_at timestamptz, first_published_at timestamptz)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT s.id, s.slug, s.title, s.summary, s.level, s.focus_ids, s.tips, s.drill_steps,
        s.scene, s.version, s.updated_at, u.display_name, s.published_version,
        s.published_at, s.first_published_at
    FROM public.shots s
    LEFT JOIN public.users u ON u.id = s.updated_by
    WHERE s.id = shot_id
$$;

-- The changes. Each returns an outcome: 'done', or why not.

CREATE FUNCTION app_admin_create_shot(new_slug text, new_title text, new_summary text,
                                      new_level text, new_focus text[], new_tips text[],
                                      new_steps text[], new_scene jsonb, why text)
RETURNS TABLE (outcome text, shot_id uuid)
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    me uuid := public.app_current_user_id();
    made uuid;
BEGIN
    IF me IS NULL THEN
        RAISE EXCEPTION 'no signed-in user' USING ERRCODE = 'insufficient_privilege';
    END IF;
    INSERT INTO public.shots (slug, title, summary, level, focus_ids, tips, drill_steps, scene,
                              created_by, updated_by)
    VALUES (new_slug, btrim(new_title), btrim(new_summary), new_level, new_focus, new_tips,
            new_steps, new_scene, me, me)
    ON CONFLICT (slug) DO NOTHING
    RETURNING id INTO made;
    IF made IS NULL THEN
        RETURN QUERY SELECT 'slug_taken'::text, NULL::uuid;
        RETURN;
    END IF;
    INSERT INTO public.admin_actions (admin_user_id, action, reason, details)
    VALUES (me, 'learn.create', btrim(why), jsonb_build_object(
        'shot', made, 'before', NULL, 'after', jsonb_build_object('slug', new_slug)));
    RETURN QUERY SELECT 'done'::text, made;
END;
$$;

-- Save the working copy. expected_version is the version the admin was editing: if someone
-- saved since, it's 'stale' and nothing changes.
CREATE FUNCTION app_admin_save_shot(shot_id uuid, expected_version integer, new_slug text,
                                    new_title text, new_summary text, new_level text,
                                    new_focus text[], new_tips text[], new_steps text[],
                                    new_scene jsonb)
RETURNS text
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    me uuid := public.app_current_user_id();
    old public.shots;
BEGIN
    IF me IS NULL THEN
        RAISE EXCEPTION 'no signed-in user' USING ERRCODE = 'insufficient_privilege';
    END IF;
    SELECT * INTO old FROM public.shots s WHERE s.id = shot_id FOR UPDATE;
    IF NOT FOUND THEN
        RETURN 'no_shot';
    END IF;
    IF old.version <> expected_version THEN
        RETURN 'stale';
    END IF;
    IF new_slug <> old.slug THEN
        IF old.first_published_at IS NOT NULL THEN
            RETURN 'slug_locked';
        END IF;
        PERFORM 1 FROM public.shots s WHERE s.slug = new_slug;
        IF FOUND THEN
            RETURN 'slug_taken';
        END IF;
    END IF;
    UPDATE public.shots s SET
        slug = new_slug, title = btrim(new_title), summary = btrim(new_summary),
        level = new_level, focus_ids = new_focus, tips = new_tips, drill_steps = new_steps,
        scene = new_scene, version = old.version + 1, updated_by = me, updated_at = now()
    WHERE s.id = shot_id;
    RETURN 'done';
END;
$$;

-- Publish the working copy as it is at expected_version (which the API has checked).
CREATE FUNCTION app_admin_publish_shot(shot_id uuid, expected_version integer, why text)
RETURNS text
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    me uuid := public.app_current_user_id();
    old public.shots;
BEGIN
    IF me IS NULL THEN
        RAISE EXCEPTION 'no signed-in user' USING ERRCODE = 'insufficient_privilege';
    END IF;
    SELECT * INTO old FROM public.shots s WHERE s.id = shot_id FOR UPDATE;
    IF NOT FOUND THEN
        RETURN 'no_shot';
    END IF;
    IF old.version <> expected_version THEN
        RETURN 'stale';
    END IF;
    IF old.published_version IS NOT DISTINCT FROM old.version THEN
        RETURN 'unchanged';
    END IF;
    UPDATE public.shots s SET
        published = jsonb_build_object(
            'title', old.title, 'summary', old.summary, 'level', old.level,
            'focus_ids', to_jsonb(old.focus_ids), 'tips', to_jsonb(old.tips),
            'drill_steps', to_jsonb(old.drill_steps), 'scene', old.scene),
        published_version = old.version,
        published_at = now(),
        first_published_at = coalesce(old.first_published_at, now())
    WHERE s.id = shot_id;
    INSERT INTO public.admin_actions (admin_user_id, action, reason, details)
    VALUES (me, 'learn.publish', btrim(why), jsonb_build_object(
        'shot', shot_id, 'slug', old.slug,
        'before', old.published_version, 'after', old.version));
    RETURN 'done';
END;
$$;

CREATE FUNCTION app_admin_unpublish_shot(shot_id uuid, why text) RETURNS text
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    me uuid := public.app_current_user_id();
    old public.shots;
BEGIN
    IF me IS NULL THEN
        RAISE EXCEPTION 'no signed-in user' USING ERRCODE = 'insufficient_privilege';
    END IF;
    SELECT * INTO old FROM public.shots s WHERE s.id = shot_id FOR UPDATE;
    IF NOT FOUND THEN
        RETURN 'no_shot';
    END IF;
    IF old.published IS NULL THEN
        RETURN 'unchanged';
    END IF;
    UPDATE public.shots s SET published = NULL, published_version = NULL, published_at = NULL
    WHERE s.id = shot_id;
    INSERT INTO public.admin_actions (admin_user_id, action, reason, details)
    VALUES (me, 'learn.unpublish', btrim(why), jsonb_build_object(
        'shot', shot_id, 'slug', old.slug, 'before', old.published_version, 'after', NULL));
    RETURN 'done';
END;
$$;

-- Delete a shot that isn't published. A published one has to be unpublished first.
CREATE FUNCTION app_admin_delete_shot(shot_id uuid, why text) RETURNS text
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    me uuid := public.app_current_user_id();
    old public.shots;
BEGIN
    IF me IS NULL THEN
        RAISE EXCEPTION 'no signed-in user' USING ERRCODE = 'insufficient_privilege';
    END IF;
    SELECT * INTO old FROM public.shots s WHERE s.id = shot_id FOR UPDATE;
    IF NOT FOUND THEN
        RETURN 'no_shot';
    END IF;
    IF old.published IS NOT NULL THEN
        RETURN 'published';
    END IF;
    DELETE FROM public.shots s WHERE s.id = shot_id;
    INSERT INTO public.admin_actions (admin_user_id, action, reason, details)
    VALUES (me, 'learn.delete', btrim(why), jsonb_build_object(
        'shot', shot_id, 'slug', old.slug, 'before', old.version, 'after', NULL));
    RETURN 'done';
END;
$$;

INSERT INTO features (key, area, title, description, needs_plan, rollout) VALUES
    ('learn.public', 'learn', 'Public Learn pages',
     'Published shots at /learn, open to anyone and to search engines. Only Everyone counts; '
     'Off hides every shot at once.',
     NULL, 'off');
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
    op.execute("DROP TABLE shots")
    op.execute("DELETE FROM features WHERE key = 'learn.public'")
