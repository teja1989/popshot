"""Open crews: a lead can open a crew so anyone signed in to Popshot can find it and join at once.

Revision ID: 0038
Revises: 0037
Create Date: 2026-10-16

What changes:

- `groups` gains whether the crew is open (`open_to_all`, `opened_at`), how many members it
  takes from the listing (`max_members`, 2 to 100, 12 unless the lead changes it), and whether
  Popshot's staff took it off the listing (`unlisted_at`, `unlisted_by`). A crew can be open
  only while it isn't unlisted, and only while its default court (crew courts, 0036) is one from
  the map: opening is refused otherwise, and a change that leaves the default typed (or removes
  the last court from the map) closes the crew when the change is saved, setting
  `closed_for_court_at` so its leads are told why. The lead or a co-lead opens and closes it,
  under the groups UPDATE policy, like the rest of the crew profile. The size cap only stops
  joins from the listing; invites work as before, so no crew is cut down to size.
- `group_members.joined_open_at` says when someone joined from the listing. It limits joins to
  5 a day per person (SQLSTATE PS429 past that).
- `crew_reports`: anyone can report an open crew's listing, 3 times a day (PS429 past that).
  Only staff read them, through the admin functions; you can read your own (they're in your
  data download). A deleted account's reports stay, without the name of who made them.

Who sees what: the listing (app_open_crews_near) shows an open crew's name, about, usual days
and times, the crew's name for its court and Google's ID for it (a public place), how far it
is, and how many members it has. Never who the members are, their games or anything else:
those stay members-only. People a lead removed or declined don't see the crew in the listing
and can't join it from there. Joining (app_join_open_crew) makes you an active member with a
player, at once.

When a crew opens, its members are told by push (at most once a week per crew, through
app_claim_open_notice), in a new notification category, `crew`, that they can mute.

The feature switch crew.open starts on its crews list with no crews on it: the listing only
shows crews with the switch on, and nobody can open a crew until an admin adds it.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0038"
down_revision: str | None = "0037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "popshot_app"
ADMIN_ROLE = "popshot_admin"
# The same rule as 0022 and 0035.
NO_LINKS = (
    r"'(https?://|www\.|[[:alnum:]._%+-]+@[[:alnum:]-]+\.[[:alpha:]]|"
    r"\y[[:alnum:]-]+\.(com|net|org|io|app|co|ly|me|gg|xyz|info|biz|link|site)\y)'"
)
OLD_CATEGORIES = (
    "'games', 'play_nights', 'tab', 'milestones', 'recaps', 'invites', 'requests', 'your_week', "
    "'journey'"
)
NEW_CATEGORIES = f"{OLD_CATEGORIES}, 'crew'"
REASONS = "'spam', 'unsafe', 'offensive', 'not_pickleball', 'other'"
APP_FUNCTIONS = [
    "app_open_crews_near(double precision, double precision, integer, integer)",
    "app_join_open_crew(uuid)",
    "app_claim_open_notice(uuid)",
    "app_report_open_crew(uuid, text, text)",
    "app_crew_default_on_map(uuid)",
]
ADMIN_FUNCTIONS = [
    "app_admin_open_crew_reports()",
    "app_admin_unlist_crew(uuid, text)",
    "app_admin_relist_crew(uuid, text)",
    "app_admin_dismiss_crew_reports(uuid, text)",
]

UPGRADE = f"""
ALTER TABLE groups
    ADD COLUMN open_to_all boolean NOT NULL DEFAULT false,
    ADD COLUMN opened_at timestamptz,
    ADD COLUMN open_notice_at timestamptz,
    ADD COLUMN max_members smallint NOT NULL DEFAULT 12 CHECK (max_members BETWEEN 2 AND 100),
    ADD COLUMN unlisted_at timestamptz,
    ADD COLUMN unlisted_by uuid REFERENCES users(id),
    ADD COLUMN closed_for_court_at timestamptz,
    ADD CONSTRAINT groups_open_listed CHECK (NOT open_to_all OR unlisted_at IS NULL);
CREATE INDEX groups_open_idx ON groups (id) WHERE open_to_all;
GRANT UPDATE (open_to_all, opened_at, max_members) ON groups TO {APP_ROLE};

-- Whether the crew's default court is one from the map (a Google place).
CREATE FUNCTION app_crew_default_on_map(target_group uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT EXISTS (
        SELECT 1 FROM public.crew_courts c
        WHERE c.group_id = target_group AND c.is_default AND c.place_id IS NOT NULL)
$$;
REVOKE EXECUTE ON FUNCTION app_crew_default_on_map(uuid) FROM PUBLIC;

-- Opening needs a default court from the map; opening again clears the "closed" note.
CREATE FUNCTION app_open_needs_map_court() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
    IF NEW.open_to_all AND NOT OLD.open_to_all THEN
        IF NOT public.app_crew_default_on_map(NEW.id) THEN
            RAISE EXCEPTION 'an open crew needs a default court from the map'
                USING ERRCODE = 'check_violation', CONSTRAINT = 'groups_open_needs_place';
        END IF;
        NEW.closed_for_court_at := NULL;
    END IF;
    RETURN NEW;
END;
$$;
REVOKE EXECUTE ON FUNCTION app_open_needs_map_court() FROM PUBLIC;
CREATE TRIGGER groups_open_needs_map_court BEFORE UPDATE OF open_to_all ON groups
    FOR EACH ROW EXECUTE FUNCTION app_open_needs_map_court();

-- A change to the courts that leaves the default typed closes an open crew. Checked when the
-- change is saved (deferred), so switching the default from one court to another, which
-- briefly has none, doesn't close it.
CREATE FUNCTION app_close_crew_off_map() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    target uuid := CASE WHEN TG_OP = 'DELETE' THEN OLD.group_id ELSE NEW.group_id END;
BEGIN
    UPDATE public.groups g SET open_to_all = false, closed_for_court_at = now()
    WHERE g.id = target AND g.open_to_all AND NOT public.app_crew_default_on_map(target);
    RETURN NULL;
END;
$$;
REVOKE EXECUTE ON FUNCTION app_close_crew_off_map() FROM PUBLIC;
CREATE CONSTRAINT TRIGGER crew_courts_close_open_crew AFTER UPDATE OR DELETE ON crew_courts
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION app_close_crew_off_map();

ALTER TABLE group_members ADD COLUMN joined_open_at timestamptz;
CREATE INDEX group_members_open_joins_idx ON group_members (user_id, joined_open_at)
    WHERE joined_open_at IS NOT NULL;

CREATE INDEX places_located_idx ON places (lat, lng) WHERE lat IS NOT NULL;

CREATE TABLE crew_reports (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    group_id uuid NOT NULL REFERENCES groups ON DELETE CASCADE,
    reporter_id uuid REFERENCES users(id),
    reason text NOT NULL CHECK (reason IN ({REASONS})),
    note text CHECK (char_length(btrim(note)) BETWEEN 1 AND 300 AND note !~* {NO_LINKS}),
    created_at timestamptz NOT NULL DEFAULT now(),
    resolved_at timestamptz,
    resolved_by uuid REFERENCES users(id),
    resolution text CHECK (resolution IN ('unlisted', 'dismissed')),
    CHECK ((resolved_at IS NULL) = (resolution IS NULL))
);
CREATE INDEX crew_reports_reporter_idx ON crew_reports (reporter_id, created_at);
CREATE INDEX crew_reports_open_idx ON crew_reports (group_id) WHERE resolved_at IS NULL;
ALTER TABLE crew_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE crew_reports FORCE ROW LEVEL SECURITY;
REVOKE ALL ON crew_reports FROM PUBLIC;
CREATE POLICY app_own_read ON crew_reports FOR SELECT TO {APP_ROLE}
    USING (reporter_id = app_current_user_id());
CREATE POLICY owner_definer_all ON crew_reports FOR ALL TO CURRENT_USER
    USING (true) WITH CHECK (true);
GRANT SELECT ON crew_reports TO {APP_ROLE};

-- A deleted account's reports stay (they're about the crew), without who made them.
CREATE FUNCTION app_forget_crew_reports() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
    UPDATE public.crew_reports SET reporter_id = NULL WHERE reporter_id = NEW.id;
    RETURN NEW;
END;
$$;
REVOKE EXECUTE ON FUNCTION app_forget_crew_reports() FROM PUBLIC;
CREATE TRIGGER users_forget_crew_reports AFTER UPDATE OF deleted_at ON users
    FOR EACH ROW WHEN (NEW.deleted_at IS NOT NULL AND OLD.deleted_at IS NULL)
    EXECUTE FUNCTION app_forget_crew_reports();

-- Open, listed, not deleted, and the crew.open switch on for it.
CREATE FUNCTION app_crew_listed(target_group uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT EXISTS (
        SELECT 1 FROM public.groups g
        WHERE g.id = target_group AND g.deleted_at IS NULL AND g.open_to_all
          AND g.unlisted_at IS NULL AND public.app_feature_allowed('crew.open', g.id))
$$;
REVOKE EXECUTE ON FUNCTION app_crew_listed(uuid) FROM PUBLIC;

-- Open crews within radius_km of a point, nearest first: listing fields only.
CREATE FUNCTION app_open_crews_near(
    at_lat double precision, at_lng double precision, radius_km integer, max_rows integer
) RETURNS TABLE (
    group_id uuid, name text, about text, usual_days text[], usual_times text[],
    court text, google_place_id text, distance_km numeric, members bigint,
    max_members smallint, is_full boolean, my_status text
)
LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
#variable_conflict use_column
DECLARE
    me uuid := public.app_current_user_id();
    r double precision;
    lat_span double precision;
    lng_span double precision;
BEGIN
    IF me IS NULL THEN
        RAISE EXCEPTION 'no signed-in user' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF at_lat IS NULL OR at_lng IS NULL OR at_lat NOT BETWEEN -90 AND 90
       OR at_lng NOT BETWEEN -180 AND 180 THEN
        RETURN;
    END IF;
    r := least(greatest(coalesce(radius_km, 25), 1), 100);
    lat_span := r / 111.0;
    -- Near the poles a degree of longitude shrinks to nothing: cap the box at the whole world.
    lng_span := least(r / (111.0 * greatest(cos(radians(at_lat)), 0.01)), 180);
    RETURN QUERY
    WITH near AS (
        SELECT g.id, g.name, g.about, g.usual_days, g.usual_times, d.label,
               p.google_place_id AS place, g.max_members AS cap,
               6371.0 * 2 * asin(sqrt(
                   power(sin(radians(p.lat - at_lat) / 2), 2)
                   + cos(radians(at_lat)) * cos(radians(p.lat))
                     * power(sin(radians(p.lng - at_lng) / 2), 2))) AS km
        FROM public.groups g
        JOIN public.crew_courts d ON d.group_id = g.id AND d.is_default
        JOIN public.places p ON p.id = d.place_id
        WHERE g.open_to_all AND g.deleted_at IS NULL AND g.unlisted_at IS NULL
          AND p.lat BETWEEN at_lat - lat_span AND at_lat + lat_span
          AND (lng_span >= 180 OR p.lng BETWEEN at_lng - lng_span AND at_lng + lng_span)
          AND public.app_feature_allowed('crew.open', g.id)
          -- Someone a lead removed or declined doesn't see the crew here.
          AND NOT EXISTS (
              SELECT 1 FROM public.group_members x
              WHERE x.group_id = g.id AND x.user_id = me
                AND x.status = 'removed' AND x.left_at IS NULL)
    )
    SELECT n.id, n.name, n.about, n.usual_days, n.usual_times, n.label, n.place,
           round(n.km::numeric, 1),
           c.active, n.cap, c.active >= n.cap,
           (SELECT m.status::text FROM public.group_members m
            WHERE m.group_id = n.id AND m.user_id = me AND m.status IN ('active', 'pending'))
    FROM near n
    CROSS JOIN LATERAL (
        SELECT count(*) AS active FROM public.group_members m
        WHERE m.group_id = n.id AND m.status = 'active') c
    WHERE n.km <= r
    ORDER BY n.km, n.name
    LIMIT least(greatest(coalesce(max_rows, 20), 1), 50);
END;
$$;

-- Join an open crew at once. Returns 'joined', 'already' (you're in), 'closed' (not open, or
-- not there), 'full', or 'not_allowed' (a lead removed or declined you). PS429 past 5 a day.
CREATE FUNCTION app_join_open_crew(target_group uuid) RETURNS text
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    me uuid := public.app_current_user_id();
    grp record;
    existing public.member_status;
    existing_left timestamptz;
BEGIN
    IF me IS NULL THEN
        RAISE EXCEPTION 'no signed-in user' USING ERRCODE = 'insufficient_privilege';
    END IF;
    -- Lock the crew: two people can't both take its last spot.
    SELECT g.id, g.max_members INTO grp FROM public.groups g
    WHERE g.id = target_group FOR UPDATE;
    IF NOT FOUND OR NOT public.app_crew_listed(target_group) THEN
        RETURN 'closed';
    END IF;
    SELECT m.status, m.left_at INTO existing, existing_left FROM public.group_members m
    WHERE m.group_id = target_group AND m.user_id = me;
    IF FOUND AND existing = 'active' THEN
        RETURN 'already';
    END IF;
    IF FOUND AND existing = 'removed' AND existing_left IS NULL THEN
        RETURN 'not_allowed';
    END IF;
    IF (SELECT count(*) FROM public.group_members m
        WHERE m.group_id = target_group AND m.status = 'active') >= grp.max_members THEN
        RETURN 'full';
    END IF;
    IF (SELECT count(*) FROM public.group_members m
        WHERE m.user_id = me AND m.joined_open_at > now() - interval '1 day') >= 5 THEN
        RAISE EXCEPTION 'too many open crew joins' USING ERRCODE = 'PS429';
    END IF;

    IF existing IS NULL THEN
        INSERT INTO public.group_members (group_id, user_id, role, status, joined_open_at)
        VALUES (target_group, me, 'member', 'active', now());
    ELSE
        -- Waiting on a link, or left before: in, as a member.
        UPDATE public.group_members m
        SET status = 'active', role = 'member', left_at = NULL, joined_open_at = now(),
            updated_at = now()
        WHERE m.group_id = target_group AND m.user_id = me;
    END IF;
    INSERT INTO public.players (group_id, user_id, display_name)
    SELECT target_group, me, u.display_name FROM public.users u WHERE u.id = me
    ON CONFLICT (group_id, user_id) DO NOTHING;
    INSERT INTO public.audit_log (group_id, actor_user_id, action, target_id)
    VALUES (target_group, me, 'member.joined_open', me);
    RETURN 'joined';
END;
$$;

-- When a crew opens, its members are told, at most once a week. True when it's time to tell
-- them (the API then sends the push); only the crew's lead or a co-lead can ask.
CREATE FUNCTION app_claim_open_notice(target_group uuid) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
    IF NOT public.app_is_admin(target_group) THEN
        RETURN false;
    END IF;
    UPDATE public.groups g SET open_notice_at = now()
    WHERE g.id = target_group AND g.open_to_all
      AND (g.open_notice_at IS NULL OR g.open_notice_at < now() - interval '7 days');
    RETURN FOUND;
END;
$$;

-- Report an open crew's listing. Returns 'reported', 'unchanged' (you already reported it
-- today) or 'closed' (not listed). PS429 past 3 reports a day.
CREATE FUNCTION app_report_open_crew(target_group uuid, why text, details text) RETURNS text
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    me uuid := public.app_current_user_id();
BEGIN
    IF me IS NULL THEN
        RAISE EXCEPTION 'no signed-in user' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF NOT public.app_crew_listed(target_group) THEN
        RETURN 'closed';
    END IF;
    PERFORM 1 FROM public.crew_reports r
    WHERE r.group_id = target_group AND r.reporter_id = me
      AND r.created_at > now() - interval '1 day';
    IF FOUND THEN
        RETURN 'unchanged';
    END IF;
    IF (SELECT count(*) FROM public.crew_reports r
        WHERE r.reporter_id = me AND r.created_at > now() - interval '1 day') >= 3 THEN
        RAISE EXCEPTION 'too many reports' USING ERRCODE = 'PS429';
    END IF;
    INSERT INTO public.crew_reports (group_id, reporter_id, reason, note)
    VALUES (target_group, me, why, nullif(btrim(details), ''));
    RETURN 'reported';
END;
$$;

-- Staff: crews with reports nobody has dealt with yet, most reported first.
CREATE FUNCTION app_admin_open_crew_reports() RETURNS TABLE (
    group_id uuid, name text, open_to_all boolean, unlisted_at timestamptz,
    reports bigint, reasons text[], notes text[], latest timestamptz
)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT g.id, g.name, g.open_to_all, g.unlisted_at, count(*),
           array_agg(DISTINCT r.reason ORDER BY r.reason),
           array_remove(array_agg(r.note ORDER BY r.created_at DESC), NULL),
           max(r.created_at)
    FROM public.crew_reports r
    JOIN public.groups g ON g.id = r.group_id
    WHERE r.resolved_at IS NULL AND public.app_current_user_id() IS NOT NULL
    GROUP BY g.id
    ORDER BY count(*) DESC, max(r.created_at) DESC
    LIMIT 100
$$;

-- Staff: take a crew off the listing (it closes, and its lead can't open it again until it's
-- relisted). Its open reports are settled. Returns 'no_crew', 'unchanged' or 'done'.
CREATE FUNCTION app_admin_unlist_crew(target_group uuid, why text) RETURNS text
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    me uuid := public.app_current_user_id();
    was_open boolean;
BEGIN
    IF me IS NULL THEN
        RAISE EXCEPTION 'no signed-in user' USING ERRCODE = 'insufficient_privilege';
    END IF;
    SELECT g.open_to_all INTO was_open FROM public.groups g
    WHERE g.id = target_group AND g.deleted_at IS NULL AND g.unlisted_at IS NULL FOR UPDATE;
    IF NOT FOUND THEN
        PERFORM 1 FROM public.groups g WHERE g.id = target_group AND g.deleted_at IS NULL;
        RETURN CASE WHEN FOUND THEN 'unchanged' ELSE 'no_crew' END;
    END IF;
    UPDATE public.groups g SET open_to_all = false, unlisted_at = now(), unlisted_by = me
    WHERE g.id = target_group;
    UPDATE public.crew_reports r SET resolved_at = now(), resolved_by = me, resolution = 'unlisted'
    WHERE r.group_id = target_group AND r.resolved_at IS NULL;
    INSERT INTO public.admin_actions (admin_user_id, action, group_id, reason, details)
    VALUES (me, 'crew.unlisted', target_group, btrim(why),
            jsonb_build_object('was_open', was_open));
    RETURN 'done';
END;
$$;

-- Staff: let a crew's lead list it again (it stays closed until they open it).
CREATE FUNCTION app_admin_relist_crew(target_group uuid, why text) RETURNS text
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    me uuid := public.app_current_user_id();
BEGIN
    IF me IS NULL THEN
        RAISE EXCEPTION 'no signed-in user' USING ERRCODE = 'insufficient_privilege';
    END IF;
    PERFORM 1 FROM public.groups g WHERE g.id = target_group AND g.deleted_at IS NULL;
    IF NOT FOUND THEN
        RETURN 'no_crew';
    END IF;
    UPDATE public.groups g SET unlisted_at = NULL, unlisted_by = NULL
    WHERE g.id = target_group AND g.unlisted_at IS NOT NULL;
    IF NOT FOUND THEN
        RETURN 'unchanged';
    END IF;
    INSERT INTO public.admin_actions (admin_user_id, action, group_id, reason)
    VALUES (me, 'crew.relisted', target_group, btrim(why));
    RETURN 'done';
END;
$$;

-- Staff: the reports don't need anything done; the crew stays listed.
CREATE FUNCTION app_admin_dismiss_crew_reports(target_group uuid, why text) RETURNS text
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    me uuid := public.app_current_user_id();
    settled integer;
BEGIN
    IF me IS NULL THEN
        RAISE EXCEPTION 'no signed-in user' USING ERRCODE = 'insufficient_privilege';
    END IF;
    UPDATE public.crew_reports r SET resolved_at = now(), resolved_by = me, resolution = 'dismissed'
    WHERE r.group_id = target_group AND r.resolved_at IS NULL;
    GET DIAGNOSTICS settled = ROW_COUNT;
    IF settled = 0 THEN
        RETURN 'unchanged';
    END IF;
    INSERT INTO public.admin_actions (admin_user_id, action, group_id, reason, details)
    VALUES (me, 'crew.reports_dismissed', target_group, btrim(why),
            jsonb_build_object('reports', settled));
    RETURN 'done';
END;
$$;

ALTER TABLE notification_settings DROP CONSTRAINT notification_settings_muted_check;
ALTER TABLE notification_settings ADD CONSTRAINT notification_settings_muted_check
    CHECK (muted <@ ARRAY[{NEW_CATEGORIES}]::text[]);

INSERT INTO features (key, area, title, description, rollout)
VALUES ('crew.open', 'crew', 'Open crews',
        'A lead can open a crew so anyone on Popshot can find it nearby and join.', 'crews');
"""


def upgrade() -> None:
    op.execute(UPGRADE)
    for signature in APP_FUNCTIONS:
        op.execute(f"REVOKE EXECUTE ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO {APP_ROLE}")
    for signature in ADMIN_FUNCTIONS:
        op.execute(f"REVOKE EXECUTE ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO {ADMIN_ROLE}")


def downgrade() -> None:
    op.execute("DELETE FROM feature_crews WHERE feature_key = 'crew.open'")
    op.execute("DELETE FROM features WHERE key = 'crew.open'")
    # The owner reads but doesn't update people's settings: allow it for this one change.
    op.execute(
        "CREATE POLICY downgrade_0038 ON notification_settings FOR UPDATE TO CURRENT_USER "
        "USING (true) WITH CHECK (true)"
    )
    op.execute("UPDATE notification_settings SET muted = array_remove(muted, 'crew')")
    op.execute("DROP POLICY downgrade_0038 ON notification_settings")
    op.execute(
        "ALTER TABLE notification_settings DROP CONSTRAINT notification_settings_muted_check"
    )
    op.execute(
        "ALTER TABLE notification_settings ADD CONSTRAINT notification_settings_muted_check "
        f"CHECK (muted <@ ARRAY[{OLD_CATEGORIES}]::text[])"
    )
    for signature in [*ADMIN_FUNCTIONS, *APP_FUNCTIONS]:
        op.execute(f"DROP FUNCTION {signature}")
    op.execute("DROP FUNCTION app_crew_listed(uuid)")
    op.execute("DROP TRIGGER users_forget_crew_reports ON users")
    op.execute("DROP FUNCTION app_forget_crew_reports()")
    op.execute("DROP TABLE crew_reports")
    op.execute("DROP INDEX places_located_idx")
    op.execute("DROP INDEX group_members_open_joins_idx")
    op.execute("ALTER TABLE group_members DROP COLUMN joined_open_at")
    op.execute("DROP TRIGGER crew_courts_close_open_crew ON crew_courts")
    op.execute("DROP FUNCTION app_close_crew_off_map()")
    op.execute("DROP TRIGGER groups_open_needs_map_court ON groups")
    op.execute("DROP FUNCTION app_open_needs_map_court()")
    op.execute("DROP INDEX groups_open_idx")
    op.execute("ALTER TABLE groups DROP CONSTRAINT groups_open_listed")
    for column in (
        "closed_for_court_at",
        "unlisted_by",
        "unlisted_at",
        "max_members",
        "open_notice_at",
        "opened_at",
        "open_to_all",
    ):
        op.execute(f"ALTER TABLE groups DROP COLUMN {column}")
