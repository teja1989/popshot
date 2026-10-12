"""Recaps (routes/recaps.py), against the real database."""

from typing import Any

import pytest
from sqlalchemy import Engine, text

from tests.db.conftest import People, committed_as
from tests.db.test_board_api import crew, singles  # noqa: F401  (crew is a fixture)
from tests.db.test_nights_api import plan

pytestmark = pytest.mark.db

Headers = dict[str, str]


def get(people: People, headers: Headers, path: str) -> Any:
    response = people.client.get(path, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_recaps_group_games_into_outings_with_awards(
    people: People,
    crew: dict[str, Any],  # noqa: F811
    app_engine: Engine,
) -> None:
    group_id = crew["group_id"]
    casey_id = people.user_id(crew["casey"])
    # Last month: one game.
    old = singles(people, crew, "Casey", "Gary", (11, 3))
    with committed_as(app_engine, casey_id) as conn:
        conn.execute(
            text("UPDATE matches SET played_at = now() - interval '30 days' WHERE id = :id"),
            {"id": old},
        )
    # Today: a meetup that started half an hour ago, and two games.
    night = plan(people, crew["casey"], group_id, venue="Riverside courts").json()[0]
    with committed_as(app_engine, casey_id) as conn:
        moved = conn.execute(
            text("UPDATE play_nights SET starts_at = now() - interval '30 minutes' WHERE id = :id"),
            {"id": night["id"]},
        )
        assert moved.rowcount == 1
    singles(people, crew, "Casey", "Gary", (11, 9))  # won by two
    singles(people, crew, "Sam", "Gary", (11, 4))  # Sam's first game

    listed = get(people, crew["sam"], f"/v1/groups/{group_id}/recaps")
    assert [r["games"] for r in listed] == [2, 1]
    newest = listed[0]
    assert newest["venue"] == "Riverside courts"
    assert listed[1]["venue"] is None
    assert newest["headline"]

    recap = get(people, crew["sam"], f"/v1/groups/{group_id}/recaps/{newest['key']}")
    assert [p["display_name"] for p in recap["newcomers"]] == ["Sam"]
    awards = {a["kind"]: a for a in recap["awards"]}
    assert [p["display_name"] for p in awards["close_call"]["players"]] == ["Casey"]
    assert awards["close_call"]["value"] == 1
    # Singles only: no partners to win with or to welcome.
    assert "great_partner" not in awards
    assert "welcome_wagon" not in awards
    assert {p["player"]["display_name"]: p["games"] for p in recap["played"]} == {
        "Gary": 2,
        "Casey": 1,
        "Sam": 1,
    }
    # The first-timer is welcomed first.
    assert "Sam" in recap["lines"][0]
    assert len(recap["match_ids"]) == 2


def test_recaps_are_for_members_only(people: People, crew: dict[str, Any]) -> None:  # noqa: F811
    singles(people, crew, "Casey", "Gary", (11, 3))
    group_id = crew["group_id"]
    key = get(people, crew["casey"], f"/v1/groups/{group_id}/recaps")[0]["key"]
    outsider = people.new("Olive")
    for path in (f"/v1/groups/{group_id}/recaps", f"/v1/groups/{group_id}/recaps/{key}"):
        assert people.client.get(path, headers=outsider).status_code == 404
    unknown = f"/v1/groups/{group_id}/recaps/00000000-0000-4000-8000-000000000000"
    assert people.client.get(unknown, headers=crew["casey"]).status_code == 404


def test_a_crew_with_no_games_has_no_recaps(people: People, crew: dict[str, Any]) -> None:  # noqa: F811
    assert get(people, crew["casey"], f"/v1/groups/{crew['group_id']}/recaps") == []
