"""One-time (and safe to repeat) database setup, run by an admin.

Creates the two group roles from ADR 0004 and gives the login users membership:

  popshot_owner  NOLOGIN, owns every table and function (migrations SET ROLE to it)
  popshot_app    NOLOGIN, what RLS policies and grants target

The login users are passed in. Locally and in CI they're password users; on Cloud SQL they're
the service accounts' IAM database users, so no database password exists anywhere.

Usage:
  python -m popshot_api.ops.bootstrap_db --migrator USER --api USER [--database popshot]
with the admin connection URL in POPSHOT_BOOTSTRAP_ADMIN_URL (a libpq URL, never a CLI arg,
so it can't end up in shell history or process listings).
"""

import argparse
import os
import re
import sys

import psycopg
from psycopg import sql

OWNER_ROLE = "popshot_owner"
APP_ROLE = "popshot_app"
DEFAULT_DATABASE = "popshot"
# Plain names locally; IAM service account users look like "name@project.iam".
_ROLE_NAME = re.compile(r"^[a-z][a-z0-9_.@-]{0,62}$")
_DB_NAME = re.compile(r"^[a-z][a-z0-9_]{0,62}$")

_GROUP_ATTRIBUTES = sql.SQL("NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOREPLICATION")


def _check(name: str, pattern: re.Pattern[str], what: str) -> str:
    if not pattern.fullmatch(name):
        raise ValueError(f"invalid {what}: {name!r}")
    return name


def _role_exists(conn: psycopg.Connection, role: str) -> bool:
    return conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,)).fetchone() is not None


def _ensure_group(conn: psycopg.Connection, role: str) -> None:
    if not _role_exists(conn, role):
        conn.execute(sql.SQL("CREATE ROLE {} ").format(sql.Identifier(role)) + _GROUP_ATTRIBUTES)
        return
    # Already there. A non-superuser admin can't re-assert these attributes (ALTER ROLE
    # ... NOSUPERUSER needs a superuser), so check them instead and refuse if any is unsafe.
    row = conn.execute(
        "SELECT rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole OR rolbypassrls"
        " OR rolreplication FROM pg_roles WHERE rolname = %s",
        (role,),
    ).fetchone()
    if row is None or row[0]:
        raise RuntimeError(f"role {role!r} exists with unsafe attributes; fix it by hand")


def _grant_membership(conn: psycopg.Connection, group: str, user: str, *, can_set: bool) -> None:
    if not _role_exists(conn, user):
        raise RuntimeError(f"login user {user!r} doesn't exist; create it first")
    conn.execute(
        sql.SQL("GRANT {} TO {} WITH INHERIT TRUE, SET {}").format(
            sql.Identifier(group), sql.Identifier(user), sql.SQL("TRUE" if can_set else "FALSE")
        )
    )


def bootstrap(admin_url: str, *, migrator: str, api: str, database: str = DEFAULT_DATABASE) -> None:
    migrator = _check(migrator, _ROLE_NAME, "migrator user")
    api = _check(api, _ROLE_NAME, "api user")
    database = _check(database, _DB_NAME, "database name")
    if migrator == api:
        raise ValueError("the migrator and the API must be different users")

    with psycopg.connect(admin_url, autocommit=True) as conn:
        is_super = conn.execute("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")
        superuser = bool(is_super.fetchone()[0])  # type: ignore[index]

        _ensure_group(conn, OWNER_ROLE)
        _ensure_group(conn, APP_ROLE)
        _grant_membership(conn, OWNER_ROLE, migrator, can_set=True)
        _grant_membership(conn, APP_ROLE, api, can_set=False)

        exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (database,))
        if exists.fetchone() is None:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))

        # Changing the owner requires being able to SET ROLE to it. A non-superuser admin
        # (Cloud SQL's postgres) gets that briefly and gives it back.
        if not superuser:
            conn.execute(
                sql.SQL("GRANT {} TO current_user WITH INHERIT FALSE, SET TRUE").format(
                    sql.Identifier(OWNER_ROLE)
                )
            )
        try:
            conn.execute(
                sql.SQL("ALTER DATABASE {} OWNER TO {}").format(
                    sql.Identifier(database), sql.Identifier(OWNER_ROLE)
                )
            )
        finally:
            if not superuser:
                conn.execute(
                    sql.SQL("REVOKE {} FROM current_user").format(sql.Identifier(OWNER_ROLE))
                )

        conn.execute(
            sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(sql.Identifier(database))
        )
        conn.execute(
            sql.SQL("GRANT CONNECT, TEMPORARY ON DATABASE {} TO {}").format(
                sql.Identifier(database), sql.Identifier(OWNER_ROLE)
            )
        )
        conn.execute(
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                sql.Identifier(database), sql.Identifier(APP_ROLE)
            )
        )

    db_url = psycopg.conninfo.make_conninfo(admin_url, dbname=database)
    with psycopg.connect(db_url, autocommit=True) as conn:
        # The database owner owns the public schema (PG 15+). Only it may create objects.
        conn.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
        conn.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(APP_ROLE)))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--migrator", required=True)
    parser.add_argument("--api", required=True)
    parser.add_argument("--database", default=DEFAULT_DATABASE)
    args = parser.parse_args(argv)
    admin_url = os.environ.get("POPSHOT_BOOTSTRAP_ADMIN_URL")
    if not admin_url:
        print("Set POPSHOT_BOOTSTRAP_ADMIN_URL to the admin's libpq URL.", file=sys.stderr)
        return 2
    bootstrap(admin_url, migrator=args.migrator, api=args.api, database=args.database)
    print(f"Database {args.database!r} is ready for {args.migrator!r} and {args.api!r}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
