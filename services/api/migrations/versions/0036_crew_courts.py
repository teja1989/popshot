"""Crew courts: one list of the places a crew plays, with one default (ADR 0007).

Revision ID: 0036
Revises: 0035
Create Date: 2026-10-15

Until now a crew had up to three home courts typed as text (0022), one court on the map from
Google Places (0035), and a free-text venue on each meetup. They become one list:

- `crew_courts`: up to 5 courts per crew. Each has the crew's own name for it (1 to 80
  characters, no links) and, when it was found on Google, the place (`places`, 0035: only
  Google's ID and coordinates for at most 30 days). Exactly one is the default whenever the
  crew has any: the first court added becomes it, and removing the default passes it to the
  next court in order. The same Google place can't be saved twice in one crew.
- `play_nights.court_id`: which saved court a meetup is at, when it's one of them. The venue
  text stays as it was when the meetup was planned, so renaming or removing a court never
  rewrites a meetup.

Who sees what: a crew's active members read its courts, like home courts before; people
waiting to join and everyone else see nothing. Leads and co-leads add, rename, reorder,
choose the default and remove them (the groups rules, 0001). A place is readable through a
court you can read.

Every crew's home courts and court on the map are copied in: the court on the map first, as
the default; otherwise the first home court is. The old columns stay, unread, until a later
migration removes them, so the code still running while this migration runs keeps working.

The scheduled job now refreshes and keeps the places that saved courts use.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0036"
down_revision: str | None = "0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "popshot_app"
MAX_COURTS = 5
# The same rule as 0022 and 0035.
NO_LINKS = (
    r"'(https?://|www\.|[[:alnum:]._%+-]+@[[:alnum:]-]+\.[[:alpha:]]|"
    r"\y[[:alnum:]-]+\.(com|net|org|io|app|co|ly|me|gg|xyz|info|biz|link|site)\y)'"
)


def _job_functions(used: str) -> str:
    """The job's place functions (0035), with `used` saying which places a crew uses."""
    return f"""
CREATE OR REPLACE FUNCTION app_jobs_places_to_refresh(max_places integer)
RETURNS TABLE (id uuid, google_place_id text)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT p.id, p.google_place_id FROM public.places p
    WHERE {used}
      AND (p.coords_at IS NULL OR p.coords_at < now() - interval '25 days')
    ORDER BY p.coords_at NULLS FIRST, p.id
    LIMIT max_places
$$;

CREATE OR REPLACE FUNCTION app_jobs_tidy_places() RETURNS integer
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
    WHERE NOT ({used}) AND p.created_at < now() - interval '1 day';
    GET DIAGNOSTICS dropped = ROW_COUNT;
    DELETE FROM public.place_lookups l WHERE l.at < now() - interval '2 days';
    RETURN cleared + dropped;
END;
$$;
"""


USED_BY_COURTS = "EXISTS (SELECT 1 FROM public.crew_courts c WHERE c.place_id = p.id)"
USED_BY_HOME = "EXISTS (SELECT 1 FROM public.groups g WHERE g.home_place_id = p.id)"

# Copy every crew's courts in: the court on the map first, as the default. Each step only fills
# crews that have no court of that kind yet, so it's safe to run again (the tests do).
BACKFILL = """
INSERT INTO crew_courts (group_id, place_id, label, is_default, position, created_by)
SELECT g.id, g.home_place_id, g.home_place_label, true, 0, g.created_by
FROM groups g
WHERE g.home_place_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM crew_courts c WHERE c.group_id = g.id AND c.place_id IS NOT NULL);
INSERT INTO crew_courts (group_id, label, position, created_by)
SELECT g.id, btrim(c.label), c.ord, g.created_by
FROM groups g CROSS JOIN LATERAL unnest(g.home_courts) WITH ORDINALITY AS c(label, ord)
WHERE char_length(btrim(c.label)) > 0
  AND NOT EXISTS (SELECT 1 FROM crew_courts t WHERE t.group_id = g.id AND t.place_id IS NULL)
ORDER BY g.id, c.ord;
"""

UPGRADE = f"""
CREATE TABLE crew_courts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id uuid NOT NULL REFERENCES groups (id) ON DELETE CASCADE,
    place_id uuid REFERENCES places (id),
    label text NOT NULL
        CHECK (char_length(btrim(label)) BETWEEN 1 AND 80 AND label !~* {NO_LINKS}),
    is_default boolean NOT NULL DEFAULT false,
    position smallint NOT NULL DEFAULT 0 CHECK (position BETWEEN 0 AND 100),
    created_by uuid NOT NULL REFERENCES users (id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (id, group_id)
);
CREATE UNIQUE INDEX crew_courts_one_default ON crew_courts (group_id) WHERE is_default;
CREATE UNIQUE INDEX crew_courts_place_once ON crew_courts (group_id, place_id)
    WHERE place_id IS NOT NULL;
CREATE INDEX crew_courts_group_idx ON crew_courts (group_id, position);
CREATE INDEX crew_courts_place_idx ON crew_courts (place_id) WHERE place_id IS NOT NULL;

ALTER TABLE crew_courts ENABLE ROW LEVEL SECURITY;
ALTER TABLE crew_courts FORCE ROW LEVEL SECURITY;
REVOKE ALL ON crew_courts FROM PUBLIC;
CREATE POLICY app_member_select ON crew_courts FOR SELECT TO {APP_ROLE}
    USING (app_is_member(group_id));
CREATE POLICY app_admin_insert ON crew_courts FOR INSERT TO {APP_ROLE}
    WITH CHECK (app_is_admin(group_id) AND created_by = app_current_user_id());
CREATE POLICY app_admin_update ON crew_courts FOR UPDATE TO {APP_ROLE}
    USING (app_is_admin(group_id)) WITH CHECK (app_is_admin(group_id));
CREATE POLICY app_admin_delete ON crew_courts FOR DELETE TO {APP_ROLE}
    USING (app_is_admin(group_id));
CREATE POLICY owner_definer_all ON crew_courts FOR ALL TO CURRENT_USER
    USING (true) WITH CHECK (true);
GRANT SELECT, INSERT, DELETE ON crew_courts TO {APP_ROLE};
GRANT UPDATE (label, is_default, position, updated_at) ON crew_courts TO {APP_ROLE};

-- At most {MAX_COURTS} a crew, and the first one is the default. The crew's lock makes two
-- adds at once wait for each other.
CREATE FUNCTION app_crew_courts_before_insert() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    existing integer;
BEGIN
    PERFORM pg_advisory_xact_lock(hashtextextended('crew_courts:' || NEW.group_id::text, 0));
    SELECT count(*) INTO existing FROM public.crew_courts c WHERE c.group_id = NEW.group_id;
    IF existing >= {MAX_COURTS} THEN
        RAISE EXCEPTION 'a crew saves at most {MAX_COURTS} courts'
            USING ERRCODE = 'check_violation', CONSTRAINT = 'crew_courts_limit';
    END IF;
    IF existing = 0 THEN
        NEW.is_default := true;
    END IF;
    RETURN NEW;
END;
$$;
REVOKE EXECUTE ON FUNCTION app_crew_courts_before_insert() FROM PUBLIC;
CREATE TRIGGER crew_courts_before_insert BEFORE INSERT ON crew_courts
    FOR EACH ROW EXECUTE FUNCTION app_crew_courts_before_insert();

-- Removing the default passes it to the next court in order, so a crew with courts always
-- has one.
CREATE FUNCTION app_crew_courts_after_delete() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
    IF OLD.is_default THEN
        UPDATE public.crew_courts c SET is_default = true, updated_at = now()
        WHERE c.id = (SELECT n.id FROM public.crew_courts n WHERE n.group_id = OLD.group_id
                      ORDER BY n.position, n.created_at, n.id LIMIT 1);
    END IF;
    RETURN NULL;
END;
$$;
REVOKE EXECUTE ON FUNCTION app_crew_courts_after_delete() FROM PUBLIC;
CREATE TRIGGER crew_courts_after_delete AFTER DELETE ON crew_courts
    FOR EACH ROW EXECUTE FUNCTION app_crew_courts_after_delete();

-- Which saved court a meetup is at; the venue text keeps what it was called then.
ALTER TABLE play_nights ADD COLUMN court_id uuid,
    ADD CONSTRAINT play_nights_court_fk FOREIGN KEY (court_id, group_id)
        REFERENCES crew_courts (id, group_id) ON DELETE SET NULL (court_id);
CREATE INDEX play_nights_court_idx ON play_nights (court_id) WHERE court_id IS NOT NULL;
GRANT UPDATE (court_id) ON play_nights TO {APP_ROLE};

-- A place is readable through a court you can read (crew_courts' policy applies inside).
DROP POLICY app_select ON places;
CREATE POLICY app_select ON places FOR SELECT TO {APP_ROLE}
    USING (EXISTS (SELECT 1 FROM crew_courts c WHERE c.place_id = places.id));

{BACKFILL}
{_job_functions(USED_BY_COURTS)}
"""


def upgrade() -> None:
    op.execute(UPGRADE)


def downgrade() -> None:
    op.execute(_job_functions(USED_BY_HOME))
    op.execute("DROP POLICY app_select ON places")
    op.execute(
        f"CREATE POLICY app_select ON places FOR SELECT TO {APP_ROLE} "
        "USING (EXISTS (SELECT 1 FROM groups g WHERE g.home_place_id = places.id))"
    )
    op.execute("DROP INDEX play_nights_court_idx")
    op.execute("ALTER TABLE play_nights DROP CONSTRAINT play_nights_court_fk")
    op.execute("ALTER TABLE play_nights DROP COLUMN court_id")
    op.execute("DROP TABLE crew_courts")
    op.execute("DROP FUNCTION app_crew_courts_after_delete()")
    op.execute("DROP FUNCTION app_crew_courts_before_insert()")
