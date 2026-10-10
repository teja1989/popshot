import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from hypothesis import settings as hypothesis_settings

from popshot_api.auth.verifier import VerifiedIdentity
from popshot_api.main import create_app
from popshot_api.settings import Environment, Settings
from tests.fakes import FakeTokenVerifier

hypothesis_settings.register_profile("default", deadline=None)
hypothesis_settings.register_profile("ci", deadline=None, max_examples=1000, print_blob=True)
hypothesis_settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "default"))

PROJECT_ID = "popshot-test"

ALICE = VerifiedIdentity(
    subject="alice-sub",
    email="alice@example.com",
    display_name="Alice",
    picture_url=None,
)


@pytest.fixture
def settings() -> Settings:
    return Settings(environment=Environment.TEST, firebase_project_id=PROJECT_ID)


@pytest.fixture
def verifier() -> FakeTokenVerifier:
    return FakeTokenVerifier({"alice-token": ALICE})


@pytest.fixture
def client(settings: Settings, verifier: FakeTokenVerifier) -> Iterator[TestClient]:
    with TestClient(create_app(settings, verifier)) as test_client:
        yield test_client
