"""The admin functions move from the API's role to the admin service's.

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-11

0010 and 0011 granted the admin functions to popshot_app, behind the API's admin check. The
admin pages now run in their own service (popshot_api.admin_main) whose login user is also in
popshot_admin (created by the bootstrap). This takes every admin grant away from popshot_app,
so the main API, the part of Popshot most exposed to the internet, can no longer call them
even if it were compromised.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "popshot_app"
ADMIN_ROLE = "popshot_admin"
FUNCTIONS = [
    "app_metrics_weekly(integer)",
    "app_metrics_retention(integer)",
    "app_admin_totals()",
    "app_admin_groups()",
    "app_admin_people(text, text)",
    "app_admin_person(uuid)",
    "app_admin_person_groups(uuid)",
    "app_admin_group(uuid)",
    "app_admin_group_members(uuid)",
]
VIEW_COLUMNS = "(user_id, page, target_id)"


def _move(from_role: str, to_role: str) -> None:
    for signature in FUNCTIONS:
        op.execute(f"REVOKE EXECUTE ON FUNCTION {signature} FROM {from_role}")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO {to_role}")
    op.execute(f"REVOKE INSERT {VIEW_COLUMNS} ON admin_views FROM {from_role}")
    op.execute(f"GRANT INSERT {VIEW_COLUMNS} ON admin_views TO {to_role}")
    op.execute(f"ALTER POLICY app_record_own ON admin_views TO {to_role}")


def upgrade() -> None:
    _move(APP_ROLE, ADMIN_ROLE)


def downgrade() -> None:
    _move(ADMIN_ROLE, APP_ROLE)
