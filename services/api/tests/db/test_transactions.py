"""The request's transaction commits before its response is sent.

If it committed after (FastAPI's default for dependencies with yield), a client could act
on a success before the change was visible to its next request, or be told a write
succeeded when the commit then failed.
"""

from collections.abc import Iterator, MutableMapping
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, event
from sqlalchemy.orm import Session

from popshot_api.main import create_app
from tests.conftest import make_settings
from tests.db.conftest import People

pytestmark = pytest.mark.db


@pytest.fixture
def order() -> Iterator[list[str]]:
    seen: list[str] = []

    def committed(_session: Session) -> None:
        seen.append("commit")

    event.listen(Session, "after_commit", committed)
    yield seen
    event.remove(Session, "after_commit", committed)


def test_commit_happens_before_the_response_starts(
    app_engine: Engine, people: People, order: list[str]
) -> None:
    app = create_app(make_settings(), people.verifier, app_engine)

    async def recording(scope: Any, receive: Any, send: Any) -> None:
        async def tracked_send(message: MutableMapping[str, Any]) -> None:
            if message["type"] == "http.response.start":
                order.append("response")
            await send(message)

        await app(scope, receive, tracked_send)

    headers = people.new("Casey")
    with TestClient(recording) as client:
        order.clear()
        response = client.post("/v1/groups", json={"name": "Order Check"}, headers=headers)
    assert response.status_code == 201, response.text
    assert order[:2] == ["commit", "response"]
