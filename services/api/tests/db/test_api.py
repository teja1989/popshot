"""The API end to end against the real database, with fake tokens."""

import time
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text

from popshot_api.auth.verifier import VerifiedIdentity
from popshot_api.db import UnsafeDatabaseRoleError
from popshot_api.main import create_app
from tests.conftest import make_settings
from tests.db.conftest import as_user
from tests.fakes import FakeTokenVerifier

pytestmark = pytest.mark.db

NEWCOMER = VerifiedIdentity(
    subject="api-test-newcomer",
    email="newcomer@example.com",
    display_name="  " + "N" * 100,
    picture_url="http://insecure.example.com/a.png",
    auth_time=int(time.time()),
)


@pytest.fixture
def client(app_engine: Engine) -> Iterator[TestClient]:
    verifier = FakeTokenVerifier({"newcomer-token": NEWCOMER})
    app = create_app(make_settings(), verifier, app_engine)
    with TestClient(app) as test_client:
        yield test_client


def test_first_request_creates_the_user(client: TestClient, app_engine: Engine) -> None:
    response = client.get("/v1/me", headers={"Authorization": "Bearer newcomer-token"})
    assert response.status_code == 200
    body = response.json()
    assert body["display_name"] == "N" * 80
    assert body["avatar_url"] is None

    again = client.get("/v1/me", headers={"Authorization": "Bearer newcomer-token"})
    assert again.json()["id"] == body["id"]

    # We keep no email address (SECURITY.md: only account ID, name and avatar).
    with as_user(app_engine, body["id"]) as conn:
        columns = set(conn.execute(text("SELECT * FROM users LIMIT 0")).keys())
    assert "email" not in columns


def test_unauthenticated_request_never_touches_the_database(client: TestClient) -> None:
    assert client.get("/v1/me").status_code == 401


def test_startup_refuses_owner_role(owner_url: str) -> None:
    engine = create_engine(owner_url)
    app = create_app(make_settings(), FakeTokenVerifier(), engine)
    with pytest.raises(UnsafeDatabaseRoleError), TestClient(app):
        pass
