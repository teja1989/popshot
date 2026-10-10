"""Alembic environment. Runs online only, as a member of popshot_owner.

The login user (popshot_migrator locally, the migrator service account's IAM user on Cloud
SQL) switches to popshot_owner first, so every object is owned by the group role and the
owner policies created with TO CURRENT_USER target popshot_owner.
"""

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from popshot_api.db import APP_ROLE, OWNER_ROLE, MetadataAccessToken, use_iam_token_as_password

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
    if os.environ.get("POPSHOT_DATABASE_IAM_AUTH", "").lower() == "true":
        use_iam_token_as_password(engine, MetadataAccessToken())
    with engine.begin() as connection:
        role = connection.execute(
            text(
                "SELECT rolsuper, pg_has_role(current_user, :app, 'MEMBER') AS is_app "
                "FROM pg_roles WHERE rolname = current_user"
            ),
            {"app": APP_ROLE},
        ).one()
        if role.is_app:
            raise RuntimeError(f"Refusing to run migrations as a member of {APP_ROLE}.")
        if role.rolsuper:
            # Objects would be owned by the superuser and owner policies would target it.
            raise RuntimeError("Refusing to run migrations as a superuser.")
        connection.execute(text(f"SET ROLE {OWNER_ROLE}"))

        context.configure(connection=connection, target_metadata=None)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    raise RuntimeError("Offline (SQL script) migrations aren't supported.")
run_migrations_online()
