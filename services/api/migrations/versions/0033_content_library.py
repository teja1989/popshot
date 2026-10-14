"""The content library: videos and articles an admin picks, tagged by skill and level.

Revision ID: 0033
Revises: 0032
Create Date: 2026-10-14

content_items holds the links. Only an admin adds or changes them, through the functions
below, which log every change in admin_actions (0013) with a reason, like feature switches
(0027). Players read published items only, through app_published_content: the app role has
no direct access to the table, so a draft can't leak and nothing can write.

Links are https only, with no user name, password or port, and the host must be on
content_hosts (YouTube to start; an admin can add a site, with a reason). A trigger checks
that on every insert and update, so even a function with a bug can't store another link.
Links open outside the app; nothing is embedded, so the web's security policy is unchanged.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0033"
down_revision: str | None = "0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "popshot_app"
ADMIN_ROLE = "popshot_admin"
APP_FUNCTIONS = ["app_published_content(text[], text)"]
ADMIN_FUNCTIONS = [
    "app_admin_content()",
    "app_admin_content_hosts()",
    "app_admin_add_content(text, text, text, text, text[], text[], integer, text)",
    "app_admin_edit_content(uuid, text, text, text, text, text[], text[], integer, text)",
    "app_admin_set_content_status(uuid, text, text)",
    "app_admin_add_content_host(text, text)",
]
PRIVATE_FUNCTIONS = ["app_content_url_host(text)", "app_content_check_url()"]

UPGRADE = """
CREATE TABLE content_hosts (
    host text PRIMARY KEY
        CHECK (host ~ '^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$'
               AND char_length(host) <= 100),
    added_by uuid REFERENCES users (id) ON DELETE SET NULL,
    added_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE content_items (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    kind text NOT NULL CHECK (kind IN ('video', 'article')),
    url text NOT NULL UNIQUE CHECK (char_length(url) <= 500),
    title text NOT NULL CHECK (char_length(btrim(title)) BETWEEN 1 AND 120),
    source text NOT NULL CHECK (char_length(btrim(source)) BETWEEN 1 AND 60),
    -- The skills it helps with, from the focus list (0003).
    skills text[] NOT NULL
        CHECK (cardinality(skills) BETWEEN 1 AND 4 AND app_valid_focus_ids(skills)),
    -- Who it suits; empty means everyone.
    levels text[] NOT NULL DEFAULT '{}'
        CHECK (levels <@ ARRAY['beginner', 'intermediate', 'advanced', 'expert']),
    minutes integer CHECK (minutes BETWEEN 1 AND 120),
    status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published')),
    added_by uuid REFERENCES users (id) ON DELETE SET NULL,
    updated_by uuid REFERENCES users (id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX content_items_published_idx ON content_items USING gin (skills)
    WHERE status = 'published';

ALTER TABLE content_hosts ENABLE ROW LEVEL SECURITY;
ALTER TABLE content_hosts FORCE ROW LEVEL SECURITY;
ALTER TABLE content_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE content_items FORCE ROW LEVEL SECURITY;
REVOKE ALL ON content_hosts, content_items FROM PUBLIC;
-- No role reads or writes them directly: only the functions below (and migrations).
CREATE POLICY owner_definer_all ON content_hosts FOR ALL TO CURRENT_USER
    USING (true) WITH CHECK (true);
CREATE POLICY owner_definer_all ON content_items FOR ALL TO CURRENT_USER
    USING (true) WITH CHECK (true);

INSERT INTO content_hosts (host) VALUES ('youtube.com'), ('www.youtube.com'), ('youtu.be');

-- The host of an https link with no user name, password or port; null for anything else.
CREATE FUNCTION app_content_url_host(link text) RETURNS text
LANGUAGE sql IMMUTABLE
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT CASE
        WHEN link ~ '^https://[A-Za-z0-9.-]+(/[^[:space:]]*)?$'
        THEN lower(substring(link FROM '^https://([A-Za-z0-9.-]+)'))
    END
$$;

-- Every stored link is an allowed https link.
CREATE FUNCTION app_content_check_url() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM public.content_hosts h
        WHERE h.host = public.app_content_url_host(NEW.url)
    ) THEN
        RAISE EXCEPTION 'link not allowed' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER content_items_check_url
    BEFORE INSERT OR UPDATE OF url ON content_items
    FOR EACH ROW EXECUTE FUNCTION app_content_check_url();

-- For players: published items for any of these skills (all of them, if none) that suit
-- this level (or every level), the closest match first. At most 12.
CREATE FUNCTION app_published_content(for_skills text[], for_level text)
RETURNS TABLE (id uuid, kind text, url text, title text, source text, skills text[],
               minutes integer)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT c.id, c.kind, c.url, c.title, c.source, c.skills, c.minutes
    FROM public.content_items c
    WHERE public.app_current_user_id() IS NOT NULL
      AND c.status = 'published'
      AND (cardinality(for_skills) = 0 OR c.skills && for_skills)
      AND (cardinality(c.levels) = 0 OR for_level IS NULL OR for_level = ANY(c.levels))
    ORDER BY (SELECT count(*) FROM unnest(c.skills) s WHERE s = ANY(for_skills)) DESC,
             c.updated_at DESC, c.id
    LIMIT 12
$$;

-- Admin: everything, drafts too, newest first.
CREATE FUNCTION app_admin_content()
RETURNS TABLE (id uuid, kind text, url text, title text, source text, skills text[],
               levels text[], minutes integer, status text, updated_at timestamptz,
               updated_by_name text)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT c.id, c.kind, c.url, c.title, c.source, c.skills, c.levels, c.minutes, c.status,
           c.updated_at, u.display_name
    FROM public.content_items c
    LEFT JOIN public.users u ON u.id = c.updated_by
    ORDER BY c.updated_at DESC, c.id
    LIMIT 1000
$$;

CREATE FUNCTION app_admin_content_hosts() RETURNS TABLE (host text, added_at timestamptz)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT h.host, h.added_at FROM public.content_hosts h ORDER BY h.host
$$;

-- The changes. Each returns an outcome: 'done', or why not, and logs each 'done' with the
-- reason, in the same transaction. Bad values raise (the table's checks), as for any write.

CREATE FUNCTION app_admin_add_content(new_kind text, new_url text, new_title text,
                                      new_source text, new_skills text[], new_levels text[],
                                      new_minutes integer, why text)
RETURNS TABLE (outcome text, id uuid)
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
    IF NOT EXISTS (SELECT 1 FROM public.content_hosts h
                   WHERE h.host = public.app_content_url_host(new_url)) THEN
        RETURN QUERY SELECT 'bad_link'::text, NULL::uuid;
        RETURN;
    END IF;
    INSERT INTO public.content_items
        (kind, url, title, source, skills, levels, minutes, added_by, updated_by)
    VALUES (new_kind, new_url, btrim(new_title), btrim(new_source), new_skills, new_levels,
            new_minutes, me, me)
    ON CONFLICT (url) DO NOTHING
    RETURNING content_items.id INTO made;
    IF made IS NULL THEN
        RETURN QUERY SELECT 'duplicate'::text, NULL::uuid;
        RETURN;
    END IF;
    INSERT INTO public.admin_actions (admin_user_id, action, reason, details)
    VALUES (me, 'content.add', btrim(why), jsonb_build_object(
        'item', made, 'before', NULL, 'after', jsonb_build_object(
            'url', new_url, 'title', btrim(new_title), 'skills', new_skills)));
    RETURN QUERY SELECT 'done'::text, made;
END;
$$;

CREATE FUNCTION app_admin_edit_content(item uuid, new_kind text, new_url text, new_title text,
                                       new_source text, new_skills text[], new_levels text[],
                                       new_minutes integer, why text)
RETURNS text
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    me uuid := public.app_current_user_id();
    old public.content_items;
BEGIN
    IF me IS NULL THEN
        RAISE EXCEPTION 'no signed-in user' USING ERRCODE = 'insufficient_privilege';
    END IF;
    SELECT * INTO old FROM public.content_items c WHERE c.id = item FOR UPDATE;
    IF NOT FOUND THEN
        RETURN 'no_item';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM public.content_hosts h
                   WHERE h.host = public.app_content_url_host(new_url)) THEN
        RETURN 'bad_link';
    END IF;
    IF new_url <> old.url AND EXISTS (SELECT 1 FROM public.content_items c
                                     WHERE c.url = new_url) THEN
        RETURN 'duplicate';
    END IF;
    UPDATE public.content_items c SET
        kind = new_kind, url = new_url, title = btrim(new_title), source = btrim(new_source),
        skills = new_skills, levels = new_levels, minutes = new_minutes,
        updated_by = me, updated_at = now()
    WHERE c.id = item;
    INSERT INTO public.admin_actions (admin_user_id, action, reason, details)
    VALUES (me, 'content.edit', btrim(why), jsonb_build_object(
        'item', item,
        'before', jsonb_build_object('url', old.url, 'title', old.title, 'skills', old.skills),
        'after', jsonb_build_object('url', new_url, 'title', btrim(new_title),
                                    'skills', new_skills)));
    RETURN 'done';
END;
$$;

CREATE FUNCTION app_admin_set_content_status(item uuid, new_status text, why text)
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
    SELECT c.status INTO before FROM public.content_items c WHERE c.id = item FOR UPDATE;
    IF NOT FOUND THEN
        RETURN 'no_item';
    END IF;
    IF before = new_status THEN
        RETURN 'unchanged';
    END IF;
    UPDATE public.content_items c SET status = new_status, updated_by = me, updated_at = now()
    WHERE c.id = item;
    INSERT INTO public.admin_actions (admin_user_id, action, reason, details)
    VALUES (me, 'content.status', btrim(why), jsonb_build_object(
        'item', item, 'before', before, 'after', new_status));
    RETURN 'done';
END;
$$;

CREATE FUNCTION app_admin_add_content_host(new_host text, why text) RETURNS text
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    me uuid := public.app_current_user_id();
BEGIN
    IF me IS NULL THEN
        RAISE EXCEPTION 'no signed-in user' USING ERRCODE = 'insufficient_privilege';
    END IF;
    INSERT INTO public.content_hosts (host, added_by) VALUES (lower(new_host), me)
    ON CONFLICT DO NOTHING;
    IF NOT FOUND THEN
        RETURN 'unchanged';
    END IF;
    INSERT INTO public.admin_actions (admin_user_id, action, reason, details)
    VALUES (me, 'content.host_add', btrim(why), jsonb_build_object(
        'host', lower(new_host), 'before', false, 'after', true));
    RETURN 'done';
END;
$$;
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
    for signature in ADMIN_FUNCTIONS + APP_FUNCTIONS:
        op.execute(f"DROP FUNCTION {signature}")
    op.execute("DROP TRIGGER content_items_check_url ON content_items")
    op.execute("DROP TABLE content_items")
    op.execute("DROP TABLE content_hosts")
    for signature in reversed(PRIVATE_FUNCTIONS):
        op.execute(f"DROP FUNCTION {signature}")
