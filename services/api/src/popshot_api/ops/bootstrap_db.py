"""One-time (and safe to repeat) database setup, run by an admin.

Creates the two group roles from ADR 0004 and gives the login users membership:

  popshot_owner  NOLOGIN, owns every table and function (migrations SET ROLE to it)
  popshot_app    NOLOGIN, what RLS policies and grants target
  popshot_jobs   NOLOGIN, the scheduled job: no table privileges, only EXECUTE on the
                 functions migrations grant it (see migration 0008)
  popshot_admin  NOLOGIN, the admin service: EXECUTE on the admin functions (migration
                 0012). Its login user is also in popshot_app, for the ordinary per-request
                 setup; the API's login user is in popshot_app only, so it can't call them.

The login users are passed in. Locally and in CI they're password users; on Cloud SQL they're
the service accounts' IAM database users, so no database password exists anywhere.

Usage:
  python -m popshot_api.ops.bootstrap_db --migrator USER --api USER [--jobs USER]
      [--admin USER] [--database popshot]
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
JOBS_ROLE = "popshot_jobs"
ADMIN_ROLE = "popshot_admin"
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


def bootstrap(  # noqa: PLR0913 (one keyword-only argument per login user)
    admin_url: str,
    *,
    migrator: str,
    api: str,
    jobs: str | None = None,
    admin: str | None = None,
    database: str = DEFAULT_DATABASE,
) -> None:
    migrator = _check(migrator, _ROLE_NAME, "migrator user")
    api = _check(api, _ROLE_NAME, "api user")
    jobs = _check(jobs, _ROLE_NAME, "jobs user") if jobs is not None else None
    admin = _check(admin, _ROLE_NAME, "admin user") if admin is not None else None
    database = _check(database, _DB_NAME, "database name")
    users = [u for u in (migrator, api, jobs, admin) if u is not None]
    if len(set(users)) != len(users):
        raise ValueError("the migrator, the API, the jobs and the admin must be different users")

    with psycopg.connect(admin_url, autocommit=True) as conn:
        is_super = conn.execute("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")
        superuser = bool(is_super.fetchone()[0])  # type: ignore[index]

        _ensure_group(conn, OWNER_ROLE)
        _ensure_group(conn, APP_ROLE)
        _ensure_group(conn, JOBS_ROLE)
        _ensure_group(conn, ADMIN_ROLE)
        _grant_membership(conn, OWNER_ROLE, migrator, can_set=True)
        _grant_membership(conn, APP_ROLE, api, can_set=False)
        if jobs is not None:
            _grant_membership(conn, JOBS_ROLE, jobs, can_set=False)
        if admin is not None:
            _grant_membership(conn, APP_ROLE, admin, can_set=False)
            _grant_membership(conn, ADMIN_ROLE, admin, can_set=False)

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
        for role in (APP_ROLE, JOBS_ROLE):
            conn.execute(
                sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                    sql.Identifier(database), sql.Identifier(role)
                )
            )

    db_url = psycopg.conninfo.make_conninfo(admin_url, dbname=database)
    with psycopg.connect(db_url, autocommit=True) as conn:
        # The database owner owns the public schema (PG 15+). Only it may create objects.
        conn.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
        for role in (APP_ROLE, JOBS_ROLE):
            conn.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(role)))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--migrator", required=True)
    parser.add_argument("--api", required=True)
    parser.add_argument("--jobs", default=None, help="the scheduled job's login user")
    parser.add_argument("--admin", default=None, help="the admin service's login user")
    parser.add_argument("--database", default=DEFAULT_DATABASE)
    args = parser.parse_args(argv)
    admin_url = os.environ.get("POPSHOT_BOOTSTRAP_ADMIN_URL")
    if not admin_url:
        print("Set POPSHOT_BOOTSTRAP_ADMIN_URL to the admin's libpq URL.", file=sys.stderr)
        return 2
    bootstrap(
        admin_url,
        migrator=args.migrator,
        api=args.api,
        jobs=args.jobs,
        admin=args.admin,
        database=args.database,
    )
    print(f"Database {args.database!r} is ready for {args.migrator!r} and {args.api!r}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
