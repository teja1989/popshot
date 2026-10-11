"""Play nights: when and where the crew plays next, and who's coming.

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-11

play_nights is one night. A night planned to repeat weekly is stored as one row per week
(sharing a series_id), so nothing has to run on a schedule to create the next one.

play_night_rsvps is each member's answer: in, maybe or out. When a night has a spot limit,
the first `spots` people to say "in" (by in_since) have a spot and the rest are on the
waitlist, in order. Nothing stores who is waitlisted: it follows from the answers, so
someone dropping out moves the next person up without anything else changing.

Both are group tables (ADR 0002 checklist): group_id, composite foreign keys, forced RLS
built on app_is_member, and isolation tests. Any active member can see nights and answer
for themselves; nights are created by any member and changed by their creator or an admin
(the API checks that; RLS keeps it inside the group).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "popshot_app"

UPGRADE = f"""
CREATE TYPE rsvp_answer AS ENUM ('in', 'maybe', 'out');

CREATE TABLE play_nights (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id uuid NOT NULL REFERENCES groups (id) ON DELETE CASCADE,
    series_id uuid,
    starts_at timestamptz NOT NULL,
    venue text NOT NULL CHECK (char_length(btrim(venue)) BETWEEN 1 AND 80),
    note text CHECK (char_length(note) <= 200),
    spots smallint CHECK (spots BETWEEN 2 AND 64),
    created_by uuid NOT NULL REFERENCES users (id),
    cancelled_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (id, group_id)
);
CREATE INDEX play_nights_group_starts_idx ON play_nights (group_id, starts_at);

CREATE TABLE play_night_rsvps (
    night_id uuid NOT NULL,
    group_id uuid NOT NULL,
    user_id uuid NOT NULL,
    answer rsvp_answer NOT NULL,
    -- When they last said "in": their place in the queue for spots. Null otherwise.
    in_since timestamptz,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (night_id, user_id),
    CHECK ((answer = 'in') = (in_since IS NOT NULL)),
    FOREIGN KEY (night_id, group_id) REFERENCES play_nights (id, group_id) ON DELETE CASCADE,
    FOREIGN KEY (group_id, user_id) REFERENCES group_members (group_id, user_id)
        ON DELETE CASCADE
);

ALTER TABLE play_nights ENABLE ROW LEVEL SECURITY;
ALTER TABLE play_nights FORCE ROW LEVEL SECURITY;
ALTER TABLE play_night_rsvps ENABLE ROW LEVEL SECURITY;
ALTER TABLE play_night_rsvps FORCE ROW LEVEL SECURITY;
REVOKE ALL ON play_nights FROM PUBLIC;
REVOKE ALL ON play_night_rsvps FROM PUBLIC;

CREATE POLICY app_member_select ON play_nights FOR SELECT TO {APP_ROLE}
    USING (app_is_member(group_id));
CREATE POLICY app_member_insert ON play_nights FOR INSERT TO {APP_ROLE}
    WITH CHECK (app_is_member(group_id) AND created_by = app_current_user_id());
CREATE POLICY app_member_update ON play_nights FOR UPDATE TO {APP_ROLE}
    USING (app_is_member(group_id)) WITH CHECK (app_is_member(group_id));

-- Everyone in the group sees the answers; you only write your own.
CREATE POLICY app_member_select ON play_night_rsvps FOR SELECT TO {APP_ROLE}
    USING (app_is_member(group_id));
CREATE POLICY app_own_write ON play_night_rsvps FOR ALL TO {APP_ROLE}
    USING (app_is_member(group_id) AND user_id = app_current_user_id())
    WITH CHECK (app_is_member(group_id) AND user_id = app_current_user_id());

GRANT SELECT, INSERT, UPDATE (starts_at, venue, note, spots, cancelled_at, updated_at)
    ON play_nights TO {APP_ROLE};
GRANT SELECT, INSERT, DELETE, UPDATE (answer, in_since, updated_at)
    ON play_night_rsvps TO {APP_ROLE};
"""


def upgrade() -> None:
    op.execute(UPGRADE)


def downgrade() -> None:
    op.execute("DROP TABLE play_night_rsvps")
    op.execute("DROP TABLE play_nights")
    op.execute("DROP TYPE rsvp_answer")
