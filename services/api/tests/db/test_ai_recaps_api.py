"""The AI commentator in recaps (ai_recap, routes/recaps.py), with a fake Gemini."""

from collections.abc import Iterator, Mapping
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from popshot_api.ai_recap import DAILY_LIMIT
from popshot_api.main import create_app
from tests.conftest import make_settings
from tests.db.conftest import People, committed_as, create
from tests.db.test_games_api import join_and_approve, log, players
from tests.fakes import FakeTokenVerifier

pytestmark = pytest.mark.db

GOOD = {"headline": "Paddles up, crew!", "lines": ["Casey and Gary kept the rallies going."]}


class FakeWriter:
    model = "gemini-test"

    def __init__(self) -> None:
        self.reply: Any = GOOD
        self.calls: list[Mapping[str, Any]] = []

    def write(self, facts: Mapping[str, Any]) -> Any:
        self.calls.append(facts)
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


@pytest.fixture
def writer() -> FakeWriter:
    return FakeWriter()


@pytest.fixture
def people(app_engine: Engine, writer: FakeWriter) -> Iterator[People]:
    app = create_app(make_settings(), FakeTokenVerifier(), app_engine, recap_writer=writer)
    with TestClient(app) as client:
        yield People(client, app.state.token_verifier)


@pytest.fixture
def crew(people: People) -> dict[str, Any]:
    """Casey (lead) and Sam, plus guest Gary."""
    casey = people.new("Casey")
    group_id = create(people, casey)["id"]
    sam = join_and_approve(people, casey, group_id, "Sam")
    people.client.post(
        f"/v1/groups/{group_id}/players", json={"display_name": "Gary"}, headers=casey
    )
    ids = {name: p["id"] for name, p in players(people, casey, group_id).items()}
    return {"group_id": group_id, "casey": casey, "sam": sam, "ids": ids}


def game(people: People, crew: dict[str, Any], a: str, b: str, score: tuple[int, int]) -> str:
    response = log(
        people,
        crew["casey"],
        crew["group_id"],
        format="singles",
        team_a=[crew["ids"][a]],
        team_b=[crew["ids"][b]],
        games=[{"team_a": score[0], "team_b": score[1]}],
    )
    assert response.status_code == 201, response.text
    match_id: str = response.json()["id"]
    return match_id


def age(app_engine: Engine, people: People, crew: dict[str, Any], interval: str) -> None:
    """Move every game in the crew back by `interval`, so the outing has settled."""
    with committed_as(app_engine, people.user_id(crew["casey"])) as conn:
        conn.execute(
            text(
                "UPDATE matches SET played_at = played_at - CAST(:i AS interval) "
                "WHERE group_id = :g"
            ),
            {"g": crew["group_id"], "i": interval},
        )


def open_recap(people: People, crew: dict[str, Any]) -> dict[str, Any]:
    group_id = crew["group_id"]
    listed = people.client.get(f"/v1/groups/{group_id}/recaps", headers=crew["sam"]).json()
    response = people.client.get(
        f"/v1/groups/{group_id}/recaps/{listed[0]['key']}", headers=crew["sam"]
    )
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def test_ai_words_wait_until_the_outing_has_settled(
    people: People, crew: dict[str, Any], writer: FakeWriter, app_engine: Engine
) -> None:
    game(people, crew, "Casey", "Gary", (11, 9))
    recap = open_recap(people, crew)
    assert recap["written_by"] == "popshot"
    assert writer.calls == []

    age(app_engine, people, crew, "2 hours")
    recap = open_recap(people, crew)
    assert recap["written_by"] == "ai"
    assert recap["headline"] == GOOD["headline"]
    assert recap["lines"] == GOOD["lines"]
    # The AI got facts: first names, counts and awards, not ids or emails.
    facts = writer.calls[0]
    assert {p["name"] for p in facts["players"]} == {"Casey", "Gary"}
    assert "@" not in repr(facts)
    assert crew["ids"]["Casey"] not in repr(facts)


def test_words_are_written_once_and_the_list_reuses_them(
    people: People, crew: dict[str, Any], writer: FakeWriter, app_engine: Engine
) -> None:
    game(people, crew, "Casey", "Gary", (11, 9))
    age(app_engine, people, crew, "2 hours")
    open_recap(people, crew)
    open_recap(people, crew)
    assert len(writer.calls) == 1
    listed = people.client.get(
        f"/v1/groups/{crew['group_id']}/recaps", headers=crew["casey"]
    ).json()
    assert listed[0]["headline"] == GOOD["headline"]
    assert len(writer.calls) == 1


def test_changed_games_are_written_about_again(
    people: People, crew: dict[str, Any], writer: FakeWriter, app_engine: Engine
) -> None:
    game(people, crew, "Casey", "Gary", (11, 9))
    age(app_engine, people, crew, "2 hours")
    open_recap(people, crew)
    # A game added to the same outing (logged as played then).
    late = game(people, crew, "Sam", "Gary", (11, 4))
    with committed_as(app_engine, people.user_id(crew["casey"])) as conn:
        conn.execute(
            text("UPDATE matches SET played_at = now() - interval '110 minutes' WHERE id = :id"),
            {"id": late},
        )
    writer.reply = {"headline": "Three players, two games!", "lines": ["Welcome, Sam!"]}
    recap = open_recap(people, crew)
    assert len(writer.calls) == 2
    assert recap["headline"] == "Three players, two games!"


@pytest.mark.parametrize(
    "reply",
    [
        {"headline": "Hi", "lines": ["Sam watched from the kitchen."]},  # Sam didn't play
        {"headline": "Hi", "lines": ["Gary lost again."]},
        {"headline": "Hi"},
        RuntimeError("Vertex is down"),
    ],
    ids=["names someone absent", "mentions losing", "wrong shape", "error"],
)
def test_bad_or_failed_replies_fall_back_and_are_not_retried_at_once(
    people: People, crew: dict[str, Any], writer: FakeWriter, app_engine: Engine, reply: Any
) -> None:
    writer.reply = reply
    game(people, crew, "Casey", "Gary", (11, 9))
    age(app_engine, people, crew, "2 hours")
    first = open_recap(people, crew)
    assert first["written_by"] == "popshot"
    assert first["headline"]
    open_recap(people, crew)
    assert len(writer.calls) == 1


def test_the_daily_limit_holds(
    people: People, crew: dict[str, Any], writer: FakeWriter, app_engine: Engine
) -> None:
    group_id = crew["group_id"]
    with committed_as(app_engine, people.user_id(crew["casey"])) as conn:
        conn.execute(
            text(
                "INSERT INTO recap_texts (group_id, outing_key, facts_hash, status, model) "
                "SELECT :g, gen_random_uuid(), repeat('c', 64), 'failed', 'gemini-test' "
                "FROM generate_series(1, :n)"
            ),
            {"g": group_id, "n": DAILY_LIMIT},
        )
    game(people, crew, "Casey", "Gary", (11, 9))
    age(app_engine, people, crew, "2 hours")
    assert open_recap(people, crew)["written_by"] == "popshot"
    assert writer.calls == []
