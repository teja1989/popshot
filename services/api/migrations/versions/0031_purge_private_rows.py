"""Deleting an account now really removes its focus lists and game notes.

Revision ID: 0031
Revises: 0030
Create Date: 2026-10-14

app_jobs_purge_user (0023) deletes a deleted account's user_focus and match_reflections rows
as the tables' owner. 0023 gave the owner a DELETE policy on both, but no SELECT policy, and
row-level security applies SELECT policies to a DELETE with a WHERE clause: so both deletes
matched no rows, without an error, and those rows stayed.

This adds the missing read policies, as the other tables the purge empties already have, and
removes what was left behind for accounts deleted before now.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0031"
down_revision: str | None = "0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ["user_focus", "match_reflections"]


def upgrade() -> None:
    for table in TABLES:
        op.execute(
            f"CREATE POLICY owner_definer_read ON {table} FOR SELECT TO CURRENT_USER USING (true)"
        )
    # What the purge should have removed already.
    for table in TABLES:
        op.execute(
            f"DELETE FROM {table} t USING users u "
            "WHERE u.id = t.user_id AND u.deleted_at IS NOT NULL"
        )


def downgrade() -> None:
    # The removed rows stay removed: they belonged to deleted accounts.
    for table in TABLES:
        op.execute(f"DROP POLICY owner_definer_read ON {table}")
