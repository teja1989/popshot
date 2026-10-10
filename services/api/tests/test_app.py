import json

import pytest
from fastapi.testclient import TestClient

from popshot_api.main import create_app
from popshot_api.settings import Environment, Settings
from tests.conftest import PROJECT_ID
from tests.fakes import FakeTokenVerifier


def test_healthz(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_security_headers_on_every_response(client: TestClient) -> None:
    for path in ("/healthz", "/v1/me", "/does-not-exist"):
        response = client.get(path)
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["x-content-type-options"] == "nosniff"


def test_me_requires_a_token(client: TestClient) -> None:
    response = client.get("/v1/me")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "header",
    ["Bearer wrong-token", "Basic YWxpY2U6cHc=", "alice-token", "Bearer "],
)
def test_me_rejects_bad_credentials(client: TestClient, header: str) -> None:
    response = client.get("/v1/me", headers={"Authorization": header})
    assert response.status_code == 401


def test_me_returns_the_verified_identity(client: TestClient) -> None:
    response = client.get("/v1/me", headers={"Authorization": "Bearer alice-token"})
    assert response.status_code == 200
    assert response.json() == {
        "email": "alice@example.com",
        "display_name": "Alice",
        "picture_url": None,
    }


def test_key_outage_is_503_not_401(client: TestClient, verifier: FakeTokenVerifier) -> None:
    verifier.keys_unavailable = True
    response = client.get("/v1/me", headers={"Authorization": "Bearer alice-token"})
    assert response.status_code == 503


@pytest.mark.parametrize(
    ("environment", "exposed"),
    [(Environment.LOCAL, True), (Environment.DEV, False), (Environment.PROD, False)],
)
def test_docs_only_exposed_locally(environment: Environment, exposed: bool) -> None:
    settings = Settings(environment=environment, firebase_project_id=PROJECT_ID)
    with TestClient(create_app(settings, FakeTokenVerifier())) as client:
        assert (client.get("/docs").status_code == 200) is exposed
        assert (client.get("/openapi.json").status_code == 200) is exposed


def test_logs_are_json_and_never_contain_tokens_or_query_strings(
    client: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    capsys.readouterr()
    client.get(
        "/v1/me?invite=secret-invite-code",
        headers={
            "Authorization": "Bearer wrong-token",
            "X-Cloud-Trace-Context": "0123456789abcdef0123456789abcdef/123;o=1",
        },
    )
    out = capsys.readouterr().out
    assert "wrong-token" not in out
    assert "secret-invite-code" not in out

    lines = [json.loads(line) for line in out.splitlines() if line.strip()]
    request_line = next(line for line in lines if line["event"] == "request")
    assert request_line["severity"] == "INFO"
    assert request_line["path"] == "/v1/me"
    assert request_line["status"] == 401
    assert request_line["trace_id"] == "0123456789abcdef0123456789abcdef"
    rejected = next(line for line in lines if line["event"] == "auth.rejected")
    assert rejected["request_id"] == request_line["request_id"]


def test_malformed_trace_header_is_ignored(
    client: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    capsys.readouterr()
    client.get("/healthz", headers={"X-Cloud-Trace-Context": '"}\ninjected'})
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
    assert all("trace_id" not in line for line in lines)
