"""A crew's time zone, so its days (and soon its recaps) follow the crew's own clock.

Revision ID: 0040
Revises: 0039
Create Date: 2026-10-17

Recaps group games by gaps between them, with no idea of a day. Grouping them by the crew's
local day needs the crew's time zone. The lead's browser sends it when a crew is created
and fills it in once for older crews; leads and co-leads can change it in settings.

Only names Postgres itself knows are kept, checked by a trigger (a CHECK can't read
pg_timezone_names), so `AT TIME ZONE` on this column can never fail inside a job.
NULL means not known yet.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0040"
down_revision: str | None = "0039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "popshot_app"

UPGRADE = f"""
ALTER TABLE groups ADD COLUMN time_zone text;
GRANT UPDATE (time_zone) ON groups TO {APP_ROLE};

CREATE FUNCTION app_known_time_zone() RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
    IF NEW.time_zone IS NOT NULL
       AND NOT EXISTS (SELECT 1 FROM pg_timezone_names WHERE name = NEW.time_zone) THEN
        RAISE EXCEPTION 'unknown time zone'
            USING ERRCODE = 'check_violation', CONSTRAINT = 'groups_time_zone_known';
    END IF;
    RETURN NEW;
END;
$$;
REVOKE EXECUTE ON FUNCTION app_known_time_zone() FROM PUBLIC;
-- Reading pg_timezone_names takes milliseconds, so only when the zone actually changes.
CREATE TRIGGER groups_time_zone_known
    BEFORE INSERT ON groups
    FOR EACH ROW WHEN (NEW.time_zone IS NOT NULL)
    EXECUTE FUNCTION app_known_time_zone();
CREATE TRIGGER groups_time_zone_changed
    BEFORE UPDATE OF time_zone ON groups
    FOR EACH ROW WHEN (NEW.time_zone IS DISTINCT FROM OLD.time_zone)
    EXECUTE FUNCTION app_known_time_zone();
"""


def upgrade() -> None:
    op.execute(UPGRADE)


def downgrade() -> None:
    op.execute("DROP TRIGGER groups_time_zone_changed ON groups")
    op.execute("DROP TRIGGER groups_time_zone_known ON groups")
    op.execute("DROP FUNCTION app_known_time_zone()")
    op.execute(f"REVOKE UPDATE (time_zone) ON groups FROM {APP_ROLE}")
    op.execute("ALTER TABLE groups DROP COLUMN time_zone")
