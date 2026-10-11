"""Private focus areas (strengths, areas to improve) and post-game reflections.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-11

Both tables are private to one person, enforced here rather than only in the API:

- user_focus: your Strengths and Areas to improve. Not on users, because group-mates can
  read users rows (for names and photos) and these must stay yours alone.
- match_reflections: what went well and what to improve, per game and person. A group
  table (ADR 0002 checklist: group_id, composite foreign keys, forced RLS, isolation test),
  but even within the group only the author can see or change a row.

Option IDs are short slugs from popshot_api.focus. The database checks their shape, the
counts and that no option is on both lists; the API checks they're real options. A
reflection with both lists empty means "skipped": it stops the prompt and counts for
nothing.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "popshot_app"
VALID_IDS = "app_valid_focus_ids(text[])"

UPGRADE = f"""
-- True when every element is a slug like 'third_shot_drop' and none repeats.
CREATE FUNCTION app_valid_focus_ids(ids text[]) RETURNS boolean
LANGUAGE sql IMMUTABLE
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT coalesce(bool_and(x ~ '^[a-z][a-z0-9_]{{0,39}}$'), true)
           AND count(*) = count(DISTINCT x)
    FROM unnest(ids) AS x
$$;

CREATE TABLE user_focus (
    user_id uuid PRIMARY KEY REFERENCES users (id) ON DELETE CASCADE,
    strengths text[] NOT NULL DEFAULT '{{}}'
        CHECK (cardinality(strengths) <= 4 AND app_valid_focus_ids(strengths)),
    improve text[] NOT NULL DEFAULT '{{}}'
        CHECK (cardinality(improve) <= 3 AND app_valid_focus_ids(improve)),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (NOT (strengths && improve))
);

CREATE TABLE match_reflections (
    match_id uuid NOT NULL,
    group_id uuid NOT NULL,
    user_id uuid NOT NULL,
    went_well text[] NOT NULL DEFAULT '{{}}'
        CHECK (cardinality(went_well) <= 3 AND app_valid_focus_ids(went_well)),
    to_improve text[] NOT NULL DEFAULT '{{}}'
        CHECK (cardinality(to_improve) <= 3 AND app_valid_focus_ids(to_improve)),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (match_id, user_id),
    CHECK (NOT (went_well && to_improve)),
    FOREIGN KEY (match_id, group_id) REFERENCES matches (id, group_id) ON DELETE CASCADE,
    FOREIGN KEY (group_id, user_id) REFERENCES group_members (group_id, user_id)
        ON DELETE CASCADE
);
CREATE INDEX match_reflections_user_idx ON match_reflections (user_id, created_at DESC);

ALTER TABLE user_focus ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_focus FORCE ROW LEVEL SECURITY;
ALTER TABLE match_reflections ENABLE ROW LEVEL SECURITY;
ALTER TABLE match_reflections FORCE ROW LEVEL SECURITY;
REVOKE ALL ON user_focus FROM PUBLIC;
REVOKE ALL ON match_reflections FROM PUBLIC;

-- Yours only.
CREATE POLICY app_own ON user_focus FOR ALL TO {APP_ROLE}
    USING (user_id = app_current_user_id())
    WITH CHECK (user_id = app_current_user_id());

-- Yours only, and only in a group you're active in. Nobody else in the group sees them.
CREATE POLICY app_own ON match_reflections FOR ALL TO {APP_ROLE}
    USING (user_id = app_current_user_id() AND app_is_member(group_id))
    WITH CHECK (user_id = app_current_user_id() AND app_is_member(group_id));

GRANT SELECT, INSERT, UPDATE (strengths, improve, updated_at) ON user_focus TO {APP_ROLE};
GRANT SELECT, INSERT, UPDATE (went_well, to_improve, updated_at) ON match_reflections
    TO {APP_ROLE};

REVOKE EXECUTE ON FUNCTION {VALID_IDS} FROM PUBLIC;
GRANT EXECUTE ON FUNCTION {VALID_IDS} TO {APP_ROLE};
"""


def upgrade() -> None:
    op.execute(UPGRADE)


def downgrade() -> None:
    op.execute("DROP TABLE match_reflections")
    op.execute("DROP TABLE user_focus")
    op.execute(f"DROP FUNCTION {VALID_IDS}")
