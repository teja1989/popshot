"""Matches can be best of 5 as well as 1 or 3.

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-12

Some crews play longer matches. Ratings already count every game on its own, so nothing
else changes. Going back down fails if any best-of-5 match exists, rather than lose games.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _limits(best_of: str, games: int) -> None:
    op.execute("ALTER TABLE matches DROP CONSTRAINT matches_best_of_check")
    op.execute(
        f"ALTER TABLE matches ADD CONSTRAINT matches_best_of_check CHECK (best_of IN ({best_of}))"
    )
    op.execute("ALTER TABLE match_games DROP CONSTRAINT match_games_game_number_check")
    op.execute(
        "ALTER TABLE match_games ADD CONSTRAINT match_games_game_number_check "
        f"CHECK (game_number BETWEEN 1 AND {games})"
    )


def upgrade() -> None:
    _limits("1, 3, 5", 5)


def downgrade() -> None:
    _limits("1, 3", 3)
