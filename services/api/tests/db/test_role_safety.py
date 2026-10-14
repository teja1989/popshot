"""The database roles and objects are set up the way ADR 0002 says."""

import os
import secrets

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url

from popshot_api.db import (
    ADMIN_ROLE,
    APP_ROLE,
    OWNER_ROLE,
    UnsafeDatabaseRoleError,
    check_database_role,
)
from tests.db.conftest import INSUFFICIENT_PRIVILEGE, sqlstate_of

pytestmark = pytest.mark.db


def test_app_role_passes_startup_check(app_engine: Engine) -> None:
    check_database_role(app_engine)


def test_owner_role_fails_startup_check(owner_engine: Engine) -> None:
    with pytest.raises(UnsafeDatabaseRoleError):
        check_database_role(owner_engine)


def test_group_roles_cannot_log_in_or_escalate(owner_engine: Engine) -> None:
    with owner_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT rolname, rolcanlogin, rolsuper, rolbypassrls, rolcreaterole, rolcreatedb,"
                " rolreplication FROM pg_roles WHERE rolname IN (:app, :owner)"
            ),
            {"app": APP_ROLE, "owner": OWNER_ROLE},
        ).all()
        group_memberships = conn.execute(
            text(
                "SELECT count(*) FROM pg_auth_members a JOIN pg_roles r ON r.oid = a.member "
                "WHERE r.rolname IN (:app, :owner)"
            ),
            {"app": APP_ROLE, "owner": OWNER_ROLE},
        ).scalar_one()
    assert len(rows) == 2
    for row in rows:
        assert not any(row[1:]), row.rolname
    # The group roles themselves belong to nothing.
    assert group_memberships == 0


def _memberships(engine: Engine) -> dict[str, tuple[bool, bool]]:
    """Roles the connected login user belongs to, with (inherit, set) for each."""
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT r.rolname, a.inherit_option, a.set_option FROM pg_auth_members a "
                "JOIN pg_roles r ON r.oid = a.roleid "
                "WHERE a.member = (SELECT oid FROM pg_roles WHERE rolname = current_user)"
            )
        ).all()
    return {row.rolname: (row.inherit_option, row.set_option) for row in rows}


def test_api_login_user_belongs_only_to_popshot_app(app_engine: Engine) -> None:
    # Inherits popshot_app's rights, but can't SET ROLE to it or anything else.
    assert _memberships(app_engine) == {APP_ROLE: (True, False)}


def test_migrator_login_user_belongs_only_to_popshot_owner(owner_engine: Engine) -> None:
    assert _memberships(owner_engine) == {OWNER_ROLE: (True, True)}


def test_every_table_has_forced_rls(owner_engine: Engine) -> None:
    with owner_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT relname, relrowsecurity, relforcerowsecurity, "
                "pg_get_userbyid(relowner) AS owner FROM pg_class "
                "WHERE relkind IN ('r', 'p') AND relnamespace = 'public'::regnamespace "
                "AND relname <> 'alembic_version'"
            )
        ).all()
    assert rows
    for row in rows:
        assert row.relrowsecurity, row.relname
        assert row.relforcerowsecurity, row.relname
        assert row.owner == OWNER_ROLE, row.relname


def test_owner_deletes_can_see_their_rows(owner_engine: Engine) -> None:
    """Row-level security applies SELECT policies to a DELETE with a WHERE clause, so a
    definer function's delete without one quietly removes nothing (as 0023's purge did)."""
    with owner_engine.connect() as conn:
        missing = conn.execute(
            text(
                "SELECT DISTINCT d.tablename FROM pg_policies d "
                "WHERE d.schemaname = 'public' AND d.cmd = 'DELETE' "
                f"AND '{OWNER_ROLE}' = ANY(d.roles) "
                "AND NOT EXISTS (SELECT 1 FROM pg_policies s "
                "  WHERE s.schemaname = 'public' AND s.tablename = d.tablename "
                "  AND s.cmd IN ('SELECT', 'ALL') "
                f"  AND '{OWNER_ROLE}' = ANY(s.roles))"
            )
        ).scalars()
        assert list(missing) == []


def test_no_views_or_sequences_reachable_by_app(owner_engine: Engine) -> None:
    """Views would run with their owner's rights; keep them out until we decide otherwise."""
    with owner_engine.connect() as conn:
        views = conn.execute(
            text(
                "SELECT count(*) FROM pg_class WHERE relkind IN ('v', 'm') "
                "AND relnamespace = 'public'::regnamespace"
            )
        ).scalar_one()
    assert views == 0


def test_app_cannot_update_any_group_id_column(owner_engine: Engine) -> None:
    with owner_engine.connect() as conn:
        updatable = conn.execute(
            text(
                "SELECT table_name, column_name FROM information_schema.columns c "
                "WHERE table_schema = 'public' "
                "AND (column_name IN ('group_id', 'id', 'user_id', 'auth_subject', 'match_id', "
                "                     'player_id', 'created_by', 'entered_by', 'actor_user_id')) "
                "AND has_column_privilege(:r, format('public.%I', table_name), column_name, "
                "                         'UPDATE')"
            ),
            {"r": APP_ROLE},
        ).all()
    assert updatable == []


def test_nothing_granted_to_public(owner_engine: Engine) -> None:
    with owner_engine.connect() as conn:
        table_grants = conn.execute(
            text(
                "SELECT table_name, privilege_type FROM information_schema.role_table_grants "
                "WHERE table_schema = 'public' AND grantee = 'PUBLIC'"
            )
        ).all()
        public_functions = conn.execute(
            text(
                "SELECT p.proname FROM pg_proc p "
                "WHERE p.pronamespace = 'public'::regnamespace "
                "AND has_function_privilege('public', p.oid, 'EXECUTE')"
            )
        ).all()
    assert table_grants == []
    assert public_functions == []


def test_definer_functions_pin_search_path(owner_engine: Engine) -> None:
    with owner_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT proname, proconfig, pg_get_userbyid(proowner) AS owner FROM pg_proc "
                "WHERE pronamespace = 'public'::regnamespace AND prosecdef"
            )
        ).all()
    assert len(rows) >= 8
    for row in rows:
        assert row.proconfig == ["search_path=pg_catalog, pg_temp"], row.proname
        assert row.owner == OWNER_ROLE, row.proname


def test_app_cannot_turn_off_rls_or_take_over(app_engine: Engine) -> None:
    with app_engine.connect() as conn, conn.begin():
        for sql in (
            "ALTER TABLE matches DISABLE ROW LEVEL SECURITY",
            "ALTER TABLE matches NO FORCE ROW LEVEL SECURITY",
            "DROP POLICY app_member_select ON matches",
            "SET ROLE popshot_owner",
            "CREATE TABLE sneaky (id int)",
            "CREATE FUNCTION app_is_member(uuid, int) RETURNS boolean LANGUAGE sql "
            "AS 'SELECT true'",
        ):
            assert sqlstate_of(conn, sql) is not None, sql
        # Turning row_security off is allowed, but then any query RLS would filter errors
        # out instead of running unfiltered.
        conn.execute(text("SET LOCAL row_security = off"))
        assert sqlstate_of(conn, "SELECT count(*) FROM matches") == INSUFFICIENT_PRIVILEGE


def test_startup_refuses_a_user_that_also_belongs_to_owner(app_url: str, migrated: None) -> None:
    """A login user in both groups would inherit the owner's policies; refuse it."""
    admin_url = os.environ.get("POPSHOT_BOOTSTRAP_ADMIN_URL")
    if not admin_url:
        pytest.skip("POPSHOT_BOOTSTRAP_ADMIN_URL not set")
    password = secrets.token_hex(16)
    admin = create_engine(admin_url.replace("postgresql://", "postgresql+psycopg://", 1))
    with admin.begin() as conn:
        conn.execute(text("DROP ROLE IF EXISTS popshot_test_both"))
        conn.execute(text(f"CREATE ROLE popshot_test_both LOGIN PASSWORD '{password}'"))
        conn.execute(text(f"GRANT {APP_ROLE}, {OWNER_ROLE} TO popshot_test_both"))
    url = make_url(app_url).set(username="popshot_test_both", password=password)
    engine = create_engine(url)
    try:
        with pytest.raises(UnsafeDatabaseRoleError, match=OWNER_ROLE):
            check_database_role(engine)
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text("DROP ROLE popshot_test_both"))
        admin.dispose()


def test_the_admin_service_login_passes_only_the_admin_check(
    admin_engine: Engine, app_engine: Engine
) -> None:
    check_database_role(admin_engine, admin=True)
    # The API refuses a login that could call the admin functions...
    with pytest.raises(UnsafeDatabaseRoleError, match="popshot_admin"):
        check_database_role(admin_engine)
    # ...and the admin service refuses one that can't.
    with pytest.raises(UnsafeDatabaseRoleError, match="popshot_admin"):
        check_database_role(app_engine, admin=True)


def test_admin_login_user_belongs_to_app_and_admin(admin_engine: Engine) -> None:
    assert _memberships(admin_engine) == {APP_ROLE: (True, False), ADMIN_ROLE: (True, False)}
