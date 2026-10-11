"""Self-rated level, the optional starting point for crew points.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-11

On users rather than the private user_focus table: crew points are worked out from every
player's games and starting point, so group-mates' requests need to read it. It's one
coarse level (beginner to expert), shown to nobody directly. Changing it later only
affects the start of the replay, and results take over within about 10 games.

app_group_levels(group) returns the level behind every player in a group the caller is an
active member of, including people who have since left (their games still count, so their
starting point must not change when they go). Row-level security would hide those users,
so it's a SECURITY DEFINER function, with a read-only owner policy on players for it.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "popshot_app"
SIGNATURE = "app_group_levels(uuid)"

LEVELS = """
CREATE FUNCTION app_group_levels(target_group uuid)
RETURNS TABLE (player_id uuid, self_level text)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT p.id, u.self_level
    FROM public.players p
    JOIN public.users u ON u.id = p.user_id
    WHERE p.group_id = target_group
      AND u.self_level IS NOT NULL
      AND public.app_is_member(target_group)
$$;
"""


def upgrade() -> None:
    op.execute(
        "ALTER TABLE users ADD COLUMN self_level text "
        "CHECK (self_level IN ('beginner', 'intermediate', 'advanced', 'expert'))"
    )
    op.execute(f"GRANT UPDATE (self_level) ON users TO {APP_ROLE}")
    op.execute(
        "CREATE POLICY owner_definer_read ON players FOR SELECT TO CURRENT_USER USING (true)"
    )
    op.execute(LEVELS)
    op.execute(f"REVOKE EXECUTE ON FUNCTION {SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {SIGNATURE} TO {APP_ROLE}")


def downgrade() -> None:
    op.execute(f"DROP FUNCTION {SIGNATURE}")
    op.execute("DROP POLICY owner_definer_read ON players")
    op.execute(f"REVOKE UPDATE (self_level) ON users FROM {APP_ROLE}")
    op.execute("ALTER TABLE users DROP COLUMN self_level")
