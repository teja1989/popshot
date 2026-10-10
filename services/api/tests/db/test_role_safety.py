"""The database roles and objects are set up the way ADR 0002 says."""

import pytest
from sqlalchemy import Engine, text

from popshot_api.db import APP_ROLE, UnsafeDatabaseRoleError, check_database_role
from tests.db.conftest import INSUFFICIENT_PRIVILEGE, sqlstate_of

pytestmark = pytest.mark.db


def test_app_role_passes_startup_check(app_engine: Engine) -> None:
    check_database_role(app_engine)


def test_owner_role_fails_startup_check(owner_engine: Engine) -> None:
    with pytest.raises(UnsafeDatabaseRoleError):
        check_database_role(owner_engine)


def test_app_role_attributes(owner_engine: Engine) -> None:
    with owner_engine.connect() as conn:
        role = conn.execute(
            text(
                "SELECT rolsuper, rolbypassrls, rolcreaterole, rolcreatedb, rolreplication "
                "FROM pg_roles WHERE rolname = :r"
            ),
            {"r": APP_ROLE},
        ).one()
        memberships = conn.execute(
            text(
                "SELECT count(*) FROM pg_auth_members WHERE member = "
                "(SELECT oid FROM pg_roles WHERE rolname = :r)"
            ),
            {"r": APP_ROLE},
        ).scalar_one()
    assert not any(role)
    assert memberships == 0


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
        assert row.owner != APP_ROLE, row.relname


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
        assert row.owner != APP_ROLE


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
