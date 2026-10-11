import os
import time
from collections.abc import Iterator
from typing import Any

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
# Never connected to: tests using this URL don't touch the database.
UNUSED_DATABASE_URL = "postgresql+psycopg://popshot_app:unused@127.0.0.1:1/none"


def make_settings(environment: Environment = Environment.TEST, **overrides: Any) -> Settings:
    return Settings(
        environment=environment,
        firebase_project_id=PROJECT_ID,
        database_url=UNUSED_DATABASE_URL,
        **overrides,
    )


ALICE = VerifiedIdentity(
    subject="alice-sub",
    email="alice@example.com",
    display_name="Alice",
    picture_url=None,
    auth_time=int(time.time()),
)


@pytest.fixture
def settings() -> Settings:
    return make_settings()


@pytest.fixture
def verifier() -> FakeTokenVerifier:
    return FakeTokenVerifier({"alice-token": ALICE})


@pytest.fixture
def client(settings: Settings, verifier: FakeTokenVerifier) -> Iterator[TestClient]:
    app = create_app(settings, verifier, verify_database_role=False)
    with TestClient(app) as test_client:
        yield test_client
