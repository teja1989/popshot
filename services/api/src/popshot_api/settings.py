"""Runtime configuration, read from POPSHOT_* environment variables."""

from enum import StrEnum
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    LOCAL = "local"
    TEST = "test"
    DEV = "dev"
    PROD = "prod"


class Settings(BaseSettings):
    """All settings come from the environment. There is no .env file loading on purpose."""

    model_config = SettingsConfigDict(env_prefix="POPSHOT_", frozen=True)

    environment: Environment = Environment.LOCAL
    # Firebase / Identity Platform project that issues the users' ID tokens.
    # Google Cloud project IDs are 6-30 chars: lowercase letters, digits and hyphens.
    firebase_project_id: str = Field(pattern=r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
    # Sign-in providers we accept. Anything else enabled by mistake in the console is rejected.
    allowed_sign_in_providers: frozenset[str] = frozenset({"google.com"})
    # SQLAlchemy URL for the popshot_app role, e.g. postgresql+psycopg://popshot_app:...@host/db
    database_url: SecretStr
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    @property
    def expose_docs(self) -> bool:
        return self.environment is Environment.LOCAL
