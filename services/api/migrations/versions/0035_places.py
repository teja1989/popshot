"""Places: a crew's home court, found with Google Places, within Google's terms and our budget.

Revision ID: 0035
Revises: 0034
Create Date: 2026-10-15

A lead or co-lead searches for the crew's court and picks one; the API looks it up with Google
Places (New) and keeps:

- in `places`: Google's place ID, which Google lets us keep for good, and the place's latitude
  and longitude, which Google lets us keep for at most 30 days. The scheduled job refreshes
  them before then and clears any it couldn't refresh, and drops places no crew uses. No name
  or address from Google is kept: Google doesn't allow it.
- on `groups`: which place is home, and the crew's own name for it, typed by the lead
  ("Riverside Park courts"), with the same no-links rule as the rest of the crew profile.

Who sees what: a crew's home place is for its members, like its home courts (0022). The app
can read a place only through a crew it can see. Places are written only by app_upsert_place,
after the API has looked the place up; the home place itself is set like the crew profile,
under the groups UPDATE policy (leads and co-leads).

Every lookup is written to `place_lookups`, which limits them (SQLSTATE PS429 past these):
60 searches and 20 picks an hour per person. Across everyone, 330 searches and 330 place
lookups (picks and the job's refreshes together) a day, past which place search rests until
tomorrow (SQLSTATE PS503). That keeps a month of full days inside Google's free monthly
allowance (10,000 of each), so it can't cost anything. Rows are kept two days, are in your
data download, and go with a deleted account.

The feature switch courts.places starts on its crews list with no crews on it: nobody has it
until an admin adds a crew.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0035"
down_revision: str | None = "0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "popshot_app"
JOBS_ROLE = "popshot_jobs"
# PostgreSQL's regular expressions: \y is a word boundary. The same rule as 0022.
NO_LINKS = (
    r"'(https?://|www\.|[[:alnum:]._%+-]+@[[:alnum:]-]+\.[[:alpha:]]|"
    r"\y[[:alnum:]-]+\.(com|net|org|io|app|co|ly|me|gg|xyz|info|biz|link|site)\y)'"
)
APP_FUNCTIONS = [
    "app_place_lookup(text)",
    "app_upsert_place(text, double precision, double precision)",
]
JOB_FUNCTIONS = [
    "app_jobs_place_lookup()",
    "app_jobs_places_to_refresh(integer)",
    "app_jobs_place_coords(uuid, double precision, double precision)",
    "app_jobs_tidy_places()",
]

UPGRADE = f"""
CREATE TABLE places (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Google's place ID, kept for good (Google's terms allow it).
    -- (Postgres caps a regular expression's repeat count at 255, so the length is separate.)
    google_place_id text NOT NULL UNIQUE
        CHECK (google_place_id ~ '^[A-Za-z0-9_-]+$' AND char_length(google_place_id) <= 300),
    -- Kept at most 30 days (Google's terms); the job refreshes or clears them.
    lat double precision CHECK (lat BETWEEN -90 AND 90),
    lng double precision CHECK (lng BETWEEN -180 AND 180),
    coords_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK ((lat IS NULL) = (lng IS NULL) AND (lat IS NULL) = (coords_at IS NULL))
);

ALTER TABLE groups
    ADD COLUMN home_place_id uuid REFERENCES places (id) ON DELETE SET NULL,
    ADD COLUMN home_place_label text CHECK (
        char_length(btrim(home_place_label)) BETWEEN 1 AND 80
        AND home_place_label !~* {NO_LINKS}
    ),
    ADD CONSTRAINT groups_home_place_named
        CHECK ((home_place_id IS NULL) = (home_place_label IS NULL));
CREATE INDEX groups_home_place_idx ON groups (home_place_id) WHERE home_place_id IS NOT NULL;
-- Set like the rest of the crew profile: the groups UPDATE policy allows leads and co-leads.
GRANT UPDATE (home_place_id, home_place_label) ON groups TO {APP_ROLE};

CREATE TABLE place_lookups (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    -- Who searched; null for the job's refreshes.
    user_id uuid REFERENCES users (id) ON DELETE CASCADE,
    kind text NOT NULL CHECK (kind IN ('search', 'pick', 'refresh')),
    at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX place_lookups_user_idx ON place_lookups (user_id, at);
CREATE INDEX place_lookups_kind_idx ON place_lookups (kind, at);

ALTER TABLE places ENABLE ROW LEVEL SECURITY;
ALTER TABLE places FORCE ROW LEVEL SECURITY;
ALTER TABLE place_lookups ENABLE ROW LEVEL SECURITY;
ALTER TABLE place_lookups FORCE ROW LEVEL SECURITY;
REVOKE ALL ON places, place_lookups FROM PUBLIC;

-- A place is readable through a crew you can see (the groups policy applies inside).
CREATE POLICY app_select ON places FOR SELECT TO {APP_ROLE}
    USING (EXISTS (SELECT 1 FROM groups g WHERE g.home_place_id = places.id));
GRANT SELECT ON places TO {APP_ROLE};
-- Your own lookups, for your data download; only the functions below write them.
CREATE POLICY app_own_read ON place_lookups FOR SELECT TO {APP_ROLE}
    USING (user_id = app_current_user_id());
GRANT SELECT ON place_lookups TO {APP_ROLE};
-- Only these functions write either table.
CREATE POLICY owner_definer_all ON places FOR ALL TO CURRENT_USER
    USING (true) WITH CHECK (true);
CREATE POLICY owner_definer_all ON place_lookups FOR ALL TO CURRENT_USER
    USING (true) WITH CHECK (true);

-- Count one lookup by the signed-in person, or refuse: PS429 past their hourly limit, PS503
-- past the day's limit for everyone. 'search' is typing in the picker; 'pick' is choosing one.
CREATE FUNCTION app_place_lookup(lookup text) RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    me uuid := public.app_current_user_id();
    hourly integer := CASE lookup WHEN 'search' THEN 60 WHEN 'pick' THEN 20 END;
BEGIN
    IF me IS NULL THEN
        RAISE EXCEPTION 'no user context' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF hourly IS NULL THEN
        RAISE EXCEPTION 'unknown lookup %', lookup USING ERRCODE = 'invalid_parameter_value';
    END IF;
    DELETE FROM public.place_lookups l WHERE l.at < now() - interval '2 days';
    IF (SELECT count(*) FROM public.place_lookups l
        WHERE l.user_id = me AND l.kind = lookup
          AND l.at > now() - interval '1 hour') >= hourly THEN
        RAISE EXCEPTION 'too many place lookups' USING ERRCODE = 'PS429';
    END IF;
    -- Picks and the job's refreshes are both Place Details lookups at Google.
    IF (SELECT count(*) FROM public.place_lookups l
        WHERE l.at >= date_trunc('day', now())
          AND (l.kind = lookup OR (lookup = 'pick' AND l.kind = 'refresh'))) >= 330 THEN
        RAISE EXCEPTION 'place search is resting until tomorrow' USING ERRCODE = 'PS503';
    END IF;
    INSERT INTO public.place_lookups (user_id, kind) VALUES (me, lookup);
END;
$$;

-- Keep a place the API has just looked up: its Google ID and fresh coordinates. Returns its id.
CREATE FUNCTION app_upsert_place(google_id text, latitude double precision,
                                 longitude double precision) RETURNS uuid
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    found_id uuid;
BEGIN
    IF public.app_current_user_id() IS NULL THEN
        RAISE EXCEPTION 'no user context' USING ERRCODE = 'insufficient_privilege';
    END IF;
    INSERT INTO public.places (google_place_id, lat, lng, coords_at)
    VALUES (google_id, latitude, longitude, now())
    ON CONFLICT (google_place_id) DO UPDATE
        SET lat = EXCLUDED.lat, lng = EXCLUDED.lng, coords_at = EXCLUDED.coords_at
    RETURNING id INTO found_id;
    RETURN found_id;
END;
$$;

-- The job: one refresh, counted against the day's place lookups. False once the day's are used.
CREATE FUNCTION app_jobs_place_lookup() RETURNS boolean
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
    IF (SELECT count(*) FROM public.place_lookups l
        WHERE l.at >= date_trunc('day', now()) AND l.kind IN ('pick', 'refresh')) >= 330 THEN
        RETURN false;
    END IF;
    INSERT INTO public.place_lookups (kind) VALUES ('refresh');
    RETURN true;
END;
$$;

-- Places a crew uses whose coordinates are 25 days old or more, oldest first.
CREATE FUNCTION app_jobs_places_to_refresh(max_places integer)
RETURNS TABLE (id uuid, google_place_id text)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT p.id, p.google_place_id FROM public.places p
    WHERE EXISTS (SELECT 1 FROM public.groups g WHERE g.home_place_id = p.id)
      AND (p.coords_at IS NULL OR p.coords_at < now() - interval '25 days')
    ORDER BY p.coords_at NULLS FIRST, p.id
    LIMIT max_places
$$;

CREATE FUNCTION app_jobs_place_coords(place uuid, latitude double precision,
                                      longitude double precision) RETURNS void
LANGUAGE sql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    UPDATE public.places SET lat = latitude, lng = longitude, coords_at = now() WHERE id = place
$$;

-- Clear coordinates older than 30 days (Google's limit), drop places no crew uses, and drop
-- lookup counts older than 2 days even when nobody searches. Returns how many places changed.
CREATE FUNCTION app_jobs_tidy_places() RETURNS integer
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    cleared integer;
    dropped integer;
BEGIN
    UPDATE public.places p SET lat = NULL, lng = NULL, coords_at = NULL
    WHERE p.coords_at < now() - interval '30 days';
    GET DIAGNOSTICS cleared = ROW_COUNT;
    DELETE FROM public.places p
    WHERE NOT EXISTS (SELECT 1 FROM public.groups g WHERE g.home_place_id = p.id)
      AND p.created_at < now() - interval '1 day';
    GET DIAGNOSTICS dropped = ROW_COUNT;
    DELETE FROM public.place_lookups l WHERE l.at < now() - interval '2 days';
    RETURN cleared + dropped;
END;
$$;

-- A deleted account's lookups go with it.
CREATE FUNCTION app_forget_place_lookups() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
    DELETE FROM public.place_lookups l WHERE l.user_id = NEW.id;
    RETURN NEW;
END;
$$;
REVOKE EXECUTE ON FUNCTION app_forget_place_lookups() FROM PUBLIC;
CREATE TRIGGER users_forget_place_lookups
    AFTER UPDATE OF deleted_at ON users
    FOR EACH ROW WHEN (NEW.deleted_at IS NOT NULL AND OLD.deleted_at IS NULL)
    EXECUTE FUNCTION app_forget_place_lookups();

INSERT INTO features (key, area, title, description, needs_plan, rollout) VALUES
    ('courts.places', 'courts', 'Find your court',
     'Leads pick the crew''s home court from Google Places and name it in their own words.',
     NULL, 'crews');
"""


def upgrade() -> None:
    op.execute(UPGRADE)
    for signature in APP_FUNCTIONS:
        op.execute(f"REVOKE EXECUTE ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO {APP_ROLE}")
    for signature in JOB_FUNCTIONS:
        op.execute(f"REVOKE EXECUTE ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO {JOBS_ROLE}")


def downgrade() -> None:
    op.execute("DELETE FROM features WHERE key = 'courts.places'")
    for signature in APP_FUNCTIONS + JOB_FUNCTIONS:
        op.execute(f"DROP FUNCTION {signature}")
    op.execute("DROP TRIGGER users_forget_place_lookups ON users")
    op.execute("DROP FUNCTION app_forget_place_lookups()")
    op.execute("DROP TABLE place_lookups")
    # The places read policy looks at groups.home_place_id, so it goes first.
    op.execute("DROP POLICY app_select ON places")
    op.execute("ALTER TABLE groups DROP CONSTRAINT groups_home_place_named")
    op.execute("ALTER TABLE groups DROP COLUMN home_place_label")
    op.execute("ALTER TABLE groups DROP COLUMN home_place_id")
    op.execute("DROP TABLE places")
