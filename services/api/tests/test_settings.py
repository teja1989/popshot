import pytest
from pydantic import ValidationError

from popshot_api.settings import Environment, Settings


def test_reads_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POPSHOT_ENVIRONMENT", "prod")
    monkeypatch.setenv("POPSHOT_FIREBASE_PROJECT_ID", "ps-prod-1234")
    settings = Settings()
    assert settings.environment is Environment.PROD
    assert settings.firebase_project_id == "ps-prod-1234"
    assert settings.allowed_sign_in_providers == frozenset({"google.com"})
    assert not settings.expose_docs


def test_project_id_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("POPSHOT_FIREBASE_PROJECT_ID", raising=False)
    with pytest.raises(ValidationError):
        Settings()


@pytest.mark.parametrize("bad", ["", "UPPER-case", "has space", "a", "x" * 31, "ends-with-"])
def test_project_id_format(bad: str) -> None:
    with pytest.raises(ValidationError):
        Settings(firebase_project_id=bad)


def test_unknown_environment_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(environment="staging", firebase_project_id="ps-dev-1234")
