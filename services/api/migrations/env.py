"""Alembic environment. Runs online only, as the migration owner role."""

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from popshot_api.db import APP_ROLE

config = context.config
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name)


def _database_url() -> str:
    url = config.attributes.get("database_url") or os.environ.get("POPSHOT_MIGRATION_DATABASE_URL")
    if not url:
        raise RuntimeError("Set POPSHOT_MIGRATION_DATABASE_URL to the migration owner's URL.")
    return str(url)


def run_migrations_online() -> None:
    engine = create_engine(_database_url(), poolclass=NullPool)
    with engine.begin() as connection:
        role = connection.execute(
            text("SELECT rolname, rolsuper FROM pg_roles WHERE rolname = current_user")
        ).one()
        if role.rolname == APP_ROLE:
            raise RuntimeError(f"Refusing to run migrations as {APP_ROLE}.")
        if role.rolsuper:
            # Objects would be owned by the superuser and owner policies would target it.
            raise RuntimeError("Refusing to run migrations as a superuser; use popshot_owner.")

        context.configure(connection=connection, target_metadata=None)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    raise RuntimeError("Offline (SQL script) migrations aren't supported.")
run_migrations_online()
