"""Recap text written by the AI commentator, kept so it's written once per outing.

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-12

A recap is worked out from the games on each read (routes/recaps.py); only the AI's words are
stored, with a hash of the facts they were written from. If the games change, the hash no
longer matches and the words are written again. A 'failed' row records an attempt that
didn't pass Popshot's checks, so it isn't retried on every view (popshot_api.ai_recap).

Members of the group read and write their group's rows, like the rest of its data.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "popshot_app"

UPGRADE = f"""
CREATE TABLE recap_texts (
    group_id uuid NOT NULL REFERENCES groups (id) ON DELETE CASCADE,
    -- The outing's first match (popshot_api.recap.Outing.key).
    outing_key uuid NOT NULL,
    facts_hash text NOT NULL CHECK (facts_hash ~ '^[0-9a-f]{{64}}$'),
    status text NOT NULL CHECK (status IN ('written', 'failed')),
    headline text CHECK (char_length(headline) BETWEEN 1 AND 120),
    lines text[] NOT NULL DEFAULT '{{}}'
        CHECK (cardinality(lines) <= 3 AND char_length(array_to_string(lines, '')) <= 600),
    model text NOT NULL CHECK (model ~ '^[a-z0-9.-]{{1,64}}$'),
    written_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (group_id, outing_key),
    CHECK (status = 'failed' OR (headline IS NOT NULL AND cardinality(lines) >= 1))
);
CREATE INDEX recap_texts_written_idx ON recap_texts (group_id, written_at);

ALTER TABLE recap_texts ENABLE ROW LEVEL SECURITY;
ALTER TABLE recap_texts FORCE ROW LEVEL SECURITY;
REVOKE ALL ON recap_texts FROM PUBLIC;

CREATE POLICY app_member_select ON recap_texts FOR SELECT TO {APP_ROLE}
    USING (app_is_member(group_id));
CREATE POLICY app_member_insert ON recap_texts FOR INSERT TO {APP_ROLE}
    WITH CHECK (app_is_member(group_id));
CREATE POLICY app_member_update ON recap_texts FOR UPDATE TO {APP_ROLE}
    USING (app_is_member(group_id)) WITH CHECK (app_is_member(group_id));

GRANT SELECT, INSERT, UPDATE (facts_hash, status, headline, lines, model, written_at)
    ON recap_texts TO {APP_ROLE};
"""


def upgrade() -> None:
    op.execute(UPGRADE)


def downgrade() -> None:
    op.execute("DROP TABLE recap_texts")
