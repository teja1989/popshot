import pytest
from pydantic import ValidationError

from popshot_api.settings import Environment, Settings


def test_reads_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POPSHOT_ENVIRONMENT", "prod")
    monkeypatch.setenv("POPSHOT_FIREBASE_PROJECT_ID", "ps-prod-1234")
    monkeypatch.setenv("POPSHOT_DATABASE_URL", "postgresql+psycopg://u:secret-pw@h/db")
    settings = Settings()
    assert settings.environment is Environment.PROD
    assert settings.firebase_project_id == "ps-prod-1234"
    assert settings.allowed_sign_in_providers == frozenset({"google.com"})
    assert not settings.expose_docs
    assert "secret-pw" not in repr(settings)
    assert settings.database_iam_auth is False
    assert settings.database_url.get_secret_value().endswith("@h/db")


@pytest.mark.parametrize("missing", ["POPSHOT_FIREBASE_PROJECT_ID", "POPSHOT_DATABASE_URL"])
def test_required_settings(monkeypatch: pytest.MonkeyPatch, missing: str) -> None:
    monkeypatch.setenv("POPSHOT_FIREBASE_PROJECT_ID", "ps-dev-1234")
    monkeypatch.setenv("POPSHOT_DATABASE_URL", "postgresql+psycopg://u:p@h/db")
    monkeypatch.delenv(missing)
    with pytest.raises(ValidationError):
        Settings()


@pytest.mark.parametrize("bad", ["", "UPPER-case", "has space", "a", "x" * 31, "ends-with-"])
def test_project_id_format(bad: str) -> None:
    with pytest.raises(ValidationError):
        Settings(firebase_project_id=bad, database_url="postgresql+psycopg://u:p@h/db")


def test_unknown_environment_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(
            environment="staging",
            firebase_project_id="ps-dev-1234",
            database_url="postgresql+psycopg://u:p@h/db",
        )


def test_iam_auth_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POPSHOT_FIREBASE_PROJECT_ID", "ps-prod-1234")
    monkeypatch.setenv(
        "POPSHOT_DATABASE_URL", "postgresql+psycopg://api-sa%40p.iam@10.0.0.3/popshot"
    )
    monkeypatch.setenv("POPSHOT_DATABASE_IAM_AUTH", "true")
    assert Settings().database_iam_auth is True


def _emulator_settings(
    environment: str = "local", firebase_project_id: str = "demo-popshot"
) -> Settings:
    return Settings(
        environment=Environment(environment),
        firebase_project_id=firebase_project_id,
        database_url="postgresql+psycopg://u:p@h/db",
        auth_emulator=True,
    )


def test_auth_emulator_off_by_default() -> None:
    settings = Settings(
        firebase_project_id="demo-popshot", database_url="postgresql+psycopg://u:p@h/db"
    )
    assert settings.auth_emulator is False


def test_auth_emulator_allowed_locally_with_a_demo_project(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("K_SERVICE", raising=False)
    assert _emulator_settings().auth_emulator is True


@pytest.mark.parametrize("environment", ["test", "dev", "prod"])
def test_auth_emulator_refused_outside_local(environment: str) -> None:
    with pytest.raises(ValidationError, match="local"):
        _emulator_settings(environment=environment)


def test_auth_emulator_refused_for_a_real_project() -> None:
    with pytest.raises(ValidationError, match="demo"):
        _emulator_settings(firebase_project_id="popshot-511218")


def test_auth_emulator_refused_on_cloud_run(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("K_SERVICE", "api")
    with pytest.raises(ValidationError, match="Cloud Run"):
        _emulator_settings()
