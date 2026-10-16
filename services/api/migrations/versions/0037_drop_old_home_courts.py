"""The crew's old court columns go: crew courts (0036, ADR 0007) replaced them.

Revision ID: 0037
Revises: 0036
Create Date: 2026-10-16

0036 copied every crew's typed home courts (`groups.home_courts`, 0022) and its court on the
map (`groups.home_place_id` and `home_place_label`, 0035) into `crew_courts`. Since then
nothing reads or writes them: the API and the screens use crew courts only. They're dropped,
with the app's right to change them.

Going back puts the columns back and fills them from crew courts the way the screens before
crew courts showed them: the default court when it's on the map (otherwise the first one
that is), and the first three typed courts.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0037"
down_revision: str | None = "0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "popshot_app"
# The same rule as 0022 and 0035.
NO_LINKS = (
    r"'(https?://|www\.|[[:alnum:]._%+-]+@[[:alnum:]-]+\.[[:alpha:]]|"
    r"\y[[:alnum:]-]+\.(com|net|org|io|app|co|ly|me|gg|xyz|info|biz|link|site)\y)'"
)

UPGRADE = f"""
REVOKE UPDATE (home_courts, home_place_id, home_place_label) ON groups FROM {APP_ROLE};
ALTER TABLE groups
    DROP CONSTRAINT groups_home_place_named,
    DROP COLUMN home_place_label,
    DROP COLUMN home_place_id,
    DROP COLUMN home_courts;
"""

# 0022's and 0035's columns as they were, then the courts copied back.
DOWNGRADE = f"""
ALTER TABLE groups
    ADD COLUMN home_courts text[] NOT NULL DEFAULT '{{}}'
        CHECK (cardinality(home_courts) <= 3
               AND char_length(array_to_string(home_courts, '')) <= 240
               AND array_to_string(home_courts, ' ') !~* {NO_LINKS}),
    ADD COLUMN home_place_id uuid REFERENCES places (id) ON DELETE SET NULL,
    ADD COLUMN home_place_label text CHECK (
        char_length(btrim(home_place_label)) BETWEEN 1 AND 80
        AND home_place_label !~* {NO_LINKS}
    ),
    ADD CONSTRAINT groups_home_place_named
        CHECK ((home_place_id IS NULL) = (home_place_label IS NULL));
CREATE INDEX groups_home_place_idx ON groups (home_place_id) WHERE home_place_id IS NOT NULL;
GRANT UPDATE (home_courts, home_place_id, home_place_label) ON groups TO {APP_ROLE};

UPDATE groups g SET home_place_id = c.place_id, home_place_label = c.label
FROM (
    SELECT DISTINCT ON (group_id) group_id, place_id, label FROM crew_courts
    WHERE place_id IS NOT NULL
    ORDER BY group_id, is_default DESC, position, created_at, id
) c
WHERE c.group_id = g.id;

UPDATE groups g SET home_courts = c.labels
FROM (
    SELECT group_id, (array_agg(label ORDER BY position, created_at, id))[1:3] AS labels
    FROM crew_courts WHERE place_id IS NULL GROUP BY group_id
) c
WHERE c.group_id = g.id;
"""


def upgrade() -> None:
    op.execute(UPGRADE)


def downgrade() -> None:
    op.execute(DOWNGRADE)
