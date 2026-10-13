"""Funnel counts include today.

Revision ID: 0025
Revises: 0024
Create Date: 2026-10-13

In 0024, app_admin_funnel_sources and app_admin_funnel_loops count daily rows (page_visits,
user_activity) with `day < until::date`. Called for "up to now", that leaves out today, so
visits read 0 on the day they happen. The last day counted is now the day the window ends
in: `day <= (until - 1 microsecond)::date`. The window stays half-open ([since, until)), so
a window ending exactly at midnight still doesn't count the next day.

The two functions are rebuilt from 0024's own text with just that bound changed, so
nothing else about them can drift. Their grants (popshot_admin only) carry over, since
CREATE OR REPLACE keeps them.
"""

import importlib.util
import re
from collections.abc import Sequence
from pathlib import Path

from alembic import op

revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FUNCTIONS = ("app_admin_funnel_sources", "app_admin_funnel_loops")
OLD_BOUND = "day < until::date"
NEW_BOUND = "day <= (until - interval '1 microsecond')::date"


def _from_0024() -> str:
    spec = importlib.util.spec_from_file_location(
        "funnel_0024", Path(__file__).with_name("0024_funnel.py")
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("can't load migration 0024")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    upgrade: str = module.UPGRADE
    return upgrade


def _functions(bound: str) -> str:
    """0024's definitions of FUNCTIONS, as CREATE OR REPLACE, with `bound` for day rows."""
    sql = _from_0024()
    blocks = []
    for name in FUNCTIONS:
        found = re.search(rf"CREATE FUNCTION {name}\(.*?\n\$\$;", sql, re.DOTALL)
        if found is None:
            raise RuntimeError(f"{name} isn't in migration 0024")
        block = found.group(0).replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1)
        if OLD_BOUND not in block:
            raise RuntimeError(f"{name} in migration 0024 has no {OLD_BOUND!r}")
        blocks.append(block.replace(OLD_BOUND, bound))
    return "\n\n".join(blocks)


def upgrade() -> None:
    op.execute(_functions(NEW_BOUND))


def downgrade() -> None:
    op.execute(_functions(OLD_BOUND))
