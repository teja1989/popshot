"""Which switches are live anywhere: for things anyone signed in can browse.

Revision ID: 0039
Revises: 0038
Create Date: 2026-10-16

Until now the app only knew a switch was on through the crews you're in (app_my_features).
Find (open crews, 0038) is for people looking for a crew, often with none yet, so its tab
shows while crew.open is live anywhere: on for everyone, or on for at least one crew that
isn't deleted. app_live_features returns the switches' keys only, never which crews.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0039"
down_revision: str | None = "0038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "popshot_app"

UPGRADE = """
CREATE FUNCTION app_live_features() RETURNS SETOF text
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT f.key FROM public.features f
    WHERE public.app_current_user_id() IS NOT NULL
      AND (f.rollout = 'everyone'
           OR (f.rollout = 'crews' AND EXISTS (
                   SELECT 1 FROM public.feature_crews c
                   JOIN public.groups g ON g.id = c.group_id AND g.deleted_at IS NULL
                   WHERE c.feature_key = f.key)))
    ORDER BY f.key
$$;
"""


def upgrade() -> None:
    op.execute(UPGRADE)
    op.execute("REVOKE EXECUTE ON FUNCTION app_live_features() FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION app_live_features() TO {APP_ROLE}")


def downgrade() -> None:
    op.execute("DROP FUNCTION app_live_features()")
