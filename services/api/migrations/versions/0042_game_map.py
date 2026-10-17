"""Your game map (docs/game-map.md): a weekly games goal, and the you.map switch.

Revision ID: 0042
Revises: 0041
Create Date: 2026-10-17

The map on You puts each player's rhythm (games a week) against a goal they choose. The goal
lives in play_goals: one row per person, yours alone (never on users, which crewmates can
read), in your data download, and deleted with your account. No row means the default goal.
It isn't in journey_settings on purpose: making that row starts your Journey's check-in clock.

The map itself is worked out from games already logged; nothing else is stored. It shows only
while 'you.map' is on for you (app_feature_on_for_me), and starts off.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0042"
down_revision: str | None = "0041"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "popshot_app"

UPGRADE = f"""
CREATE TABLE play_goals (
    user_id uuid PRIMARY KEY REFERENCES users (id) ON DELETE CASCADE,
    weekly_games smallint NOT NULL CHECK (weekly_games BETWEEN 1 AND 14),
    updated_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE play_goals ENABLE ROW LEVEL SECURITY;
ALTER TABLE play_goals FORCE ROW LEVEL SECURITY;
REVOKE ALL ON play_goals FROM PUBLIC;

-- Yours only.
CREATE POLICY app_own ON play_goals FOR ALL TO {APP_ROLE}
    USING (user_id = app_current_user_id())
    WITH CHECK (user_id = app_current_user_id());
-- For the clean-up when an account is deleted (a DELETE with a WHERE needs to read, too).
CREATE POLICY owner_definer_read ON play_goals FOR SELECT TO CURRENT_USER USING (true);
CREATE POLICY owner_definer_delete ON play_goals FOR DELETE TO CURRENT_USER USING (true);
GRANT SELECT, INSERT, UPDATE (weekly_games, updated_at) ON play_goals TO {APP_ROLE};

-- A deleted account's goal goes with it.
CREATE FUNCTION app_forget_play_goal() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
    DELETE FROM public.play_goals g WHERE g.user_id = NEW.id;
    RETURN NEW;
END;
$$;
REVOKE EXECUTE ON FUNCTION app_forget_play_goal() FROM PUBLIC;
CREATE TRIGGER users_forget_play_goal
    AFTER UPDATE OF deleted_at ON users
    FOR EACH ROW WHEN (NEW.deleted_at IS NOT NULL AND OLD.deleted_at IS NULL)
    EXECUTE FUNCTION app_forget_play_goal();

INSERT INTO features (key, area, title, description, needs_plan, rollout) VALUES
    ('you.map', 'you', 'Your game map',
     'A four-box map of your own rhythm and form on You, with a next step for each box.',
     NULL, 'crews');
"""


def upgrade() -> None:
    op.execute(UPGRADE)


def downgrade() -> None:
    op.execute("DELETE FROM features WHERE key = 'you.map'")
    op.execute("DROP TRIGGER users_forget_play_goal ON users")
    op.execute("DROP FUNCTION app_forget_play_goal()")
    op.execute("DROP TABLE play_goals")
