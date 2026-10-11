"""Runtime configuration, read from POPSHOT_* environment variables."""

import os
from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, SecretStr, model_validator
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
    # SQLAlchemy URL for the API's login user, a member of popshot_app (ADR 0005), e.g.
    # postgresql+psycopg://popshot_api:...@host/popshot
    database_url: SecretStr
    # On Cloud SQL: log in as the service account's IAM user, with a short-lived token from
    # the metadata server as the password. The URL then carries no password.
    database_iam_auth: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    # Local development only: accept unsigned tokens from the Firebase Auth emulator.
    auth_emulator: bool = False
    # Web Push (VAPID) signing key, PEM. Without it, push notifications are off.
    push_vapid_private_key: SecretStr | None = None
    # Who to contact about our push traffic, sent to push services: the app's URL.
    push_subject: str = Field(default="https://localhost", pattern=r"^https://[^\s]+$")
    # Who can open the admin page: Google account emails, comma-separated. Empty: nobody.
    # Set from the POPSHOT_ADMIN_EMAILS GitHub variable at deploy, so it isn't in the repo.
    admin_emails: str = ""

    @model_validator(mode="after")
    def _auth_emulator_is_local_only(self) -> Self:
        if not self.auth_emulator:
            return self
        if self.environment is not Environment.LOCAL:
            raise ValueError("auth_emulator is allowed only when environment is local")
        if not self.firebase_project_id.startswith("demo-"):
            raise ValueError("auth_emulator needs a demo-* Firebase project")
        # Cloud Run sets K_SERVICE in every container.
        if os.environ.get("K_SERVICE"):
            raise ValueError("auth_emulator can't be used on Cloud Run")
        return self

    @model_validator(mode="after")
    def _admin_emails_look_like_emails(self) -> Self:
        for email in self.admins:
            local, _, domain = email.partition("@")
            if not local or "." not in domain or any(c.isspace() for c in email):
                raise ValueError("admin_emails must be comma-separated email addresses")
        return self

    @property
    def admins(self) -> frozenset[str]:
        """Admin emails, lowercased."""
        return frozenset(e.strip().lower() for e in self.admin_emails.split(",") if e.strip())

    @property
    def expose_docs(self) -> bool:
        return self.environment is Environment.LOCAL
