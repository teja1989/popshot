"""Crew points and the Board, against the real database."""

from typing import Any

import pytest
from sqlalchemy import Engine, text

from popshot_api.rating import LEVEL_START, RANKED_AFTER, START
from tests.db.conftest import People, committed_as, create
from tests.db.test_games_api import edit, join_and_approve, log, players

pytestmark = pytest.mark.db

Headers = dict[str, str]


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


def singles(people: People, crew: dict[str, Any], a: str, b: str, score: tuple[int, int]) -> str:
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


def board(people: People, headers: Headers, group_id: str) -> dict[str, Any]:
    response = people.client.get(f"/v1/groups/{group_id}/board", headers=headers)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def by_name(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {r["display_name"]: r for r in rows}


def test_new_group_board_lists_everyone_getting_started(
    people: People, crew: dict[str, Any]
) -> None:
    b = board(people, crew["sam"], crew["group_id"])
    assert b["ranked"] == []
    assert b["resting"] == []
    # Members with no games are listed; a guest who never played isn't.
    rows = by_name(b["getting_started"])
    assert set(rows) == {"Casey", "Sam"}
    assert (rows["Sam"]["matches"], rows["Sam"]["to_go"], rows["Sam"]["is_me"]) == (
        0,
        RANKED_AFTER,
        True,
    )
    assert b["ranked_after"] == RANKED_AFTER


def test_ten_games_gets_you_ranked_guests_included(people: People, crew: dict[str, Any]) -> None:
    for _ in range(RANKED_AFTER):
        singles(people, crew, "Casey", "Gary", (11, 6))
    singles(people, crew, "Sam", "Gary", (11, 9))
    b = board(people, crew["sam"], crew["group_id"])
    ranked = b["ranked"]
    assert [(r["rank"], r["display_name"]) for r in ranked] == [(1, "Casey"), (2, "Gary")]
    casey, gary = ranked
    assert casey["rating"] > START > gary["rating"]
    assert gary["is_guest"] is True
    assert casey["form"] == ["W"] * 5
    assert (casey["matches"], casey["wins"]) == (RANKED_AFTER, RANKED_AFTER)
    assert casey["week_change"] is None  # no games before this week
    assert 0 < casey["reliability"] <= 100
    sam = by_name(b["getting_started"])["Sam"]
    assert (sam["matches"], sam["to_go"], sam["form"]) == (1, RANKED_AFTER - 1, ["W"])
    for row in ranked:
        assert row["rating"] == round(row["rating"], 2)
        assert 2.0 <= row["rating"] <= 6.0


def test_resting_after_sixty_days(people: People, crew: dict[str, Any], app_engine: Engine) -> None:
    ids = [singles(people, crew, "Casey", "Gary", (11, 6)) for _ in range(RANKED_AFTER)]
    with committed_as(app_engine, people.user_id(crew["casey"])) as conn:
        conn.execute(
            text("UPDATE matches SET played_at = now() - interval '61 days' WHERE id = ANY(:ids)"),
            {"ids": ids},
        )
    b = board(people, crew["casey"], crew["group_id"])
    assert b["ranked"] == []
    assert {r["display_name"] for r in b["resting"]} == {"Casey", "Gary"}
    # One new game brings Casey back.
    singles(people, crew, "Casey", "Sam", (11, 8))
    assert [
        r["display_name"] for r in board(people, crew["casey"], crew["group_id"])["ranked"]
    ] == ["Casey"]


def test_self_level_sets_the_start_and_survives_leaving(
    people: People, crew: dict[str, Any]
) -> None:
    assert people.client.put(
        "/v1/me/level", json={"level": "expert"}, headers=crew["sam"]
    ).json() == {"level": "expert"}
    assert people.client.get("/v1/me", headers=crew["sam"]).json()["self_level"] == "expert"
    assert (
        people.client.put("/v1/me/level", json={"level": "pro"}, headers=crew["sam"]).status_code
        == 422
    )

    singles(people, crew, "Sam", "Gary", (11, 9))
    rows = by_name(board(people, crew["casey"], crew["group_id"])["getting_started"])
    # An expert beating an unrated guest only 11-9 is closer than expected: a small dip.
    assert LEVEL_START["intermediate"] < rows["Sam"]["rating"] < LEVEL_START["expert"]
    gary_before = rows["Gary"]["rating"]

    # Sam leaves: Sam drops off the board, but Gary's rating (which depends on Sam's start)
    # doesn't change.
    people.client.patch(
        f"/v1/groups/{crew['group_id']}/members/{people.user_id(crew['sam'])}",
        json={"action": "remove"},
        headers=crew["casey"],
    )
    rows = by_name(board(people, crew["casey"], crew["group_id"])["getting_started"])
    assert "Sam" not in rows
    assert rows["Gary"]["rating"] == gary_before

    # Clearing it goes back to the default start.
    assert (
        people.client.put("/v1/me/level", json={"level": None}, headers=crew["sam"]).status_code
        == 200
    )
    assert people.client.get("/v1/me", headers=crew["sam"]).json()["self_level"] is None


def test_editing_a_game_rerates_everyone(people: People, crew: dict[str, Any]) -> None:
    match_id = singles(people, crew, "Casey", "Gary", (11, 3))
    before = by_name(board(people, crew["casey"], crew["group_id"])["getting_started"])
    assert before["Casey"]["rating"] > START
    edit(
        people,
        crew["casey"],
        crew["group_id"],
        match_id,
        team_a=[crew["ids"]["Casey"]],
        team_b=[crew["ids"]["Gary"]],
        games=[{"team_a": 3, "team_b": 11}],
    )
    after = by_name(board(people, crew["casey"], crew["group_id"])["getting_started"])
    assert after["Casey"]["rating"] < START < after["Gary"]["rating"]
    assert after["Casey"]["form"] == ["L"]
    people.client.delete(f"/v1/groups/{crew['group_id']}/matches/{match_id}", headers=crew["casey"])
    gone = by_name(board(people, crew["casey"], crew["group_id"])["getting_started"])
    assert gone["Casey"]["matches"] == 0
    assert "Gary" not in gone


def test_my_ratings_across_groups(people: People, crew: dict[str, Any]) -> None:
    assert people.client.get("/v1/me/ratings", headers=crew["sam"]).json() == []
    for _ in range(RANKED_AFTER):
        singles(people, crew, "Sam", "Gary", (11, 7))
    mine = people.client.get("/v1/me/ratings", headers=crew["sam"]).json()
    assert len(mine) == 1
    assert (mine[0]["group_name"], mine[0]["matches"], mine[0]["rank"], mine[0]["ranked_of"]) == (
        "Tuesday Dinkers",
        RANKED_AFTER,
        1,
        2,
    )
    assert mine[0]["rating"] > START
    # All ten were today: the 30-day trend covers them, starting from START.
    assert mine[0]["month_games"] == RANKED_AFTER
    assert mine[0]["month_change"] == pytest.approx(mine[0]["rating"] - START, abs=0.01)
    assert mine[0]["month_edge"] > 0
    assert mine[0]["trend"] in ("climbing", "steady")


def test_outsiders_cant_see_a_board(people: People, crew: dict[str, Any]) -> None:
    outsider = people.new("Jordan")
    response = people.client.get(f"/v1/groups/{crew['group_id']}/board", headers=outsider)
    assert response.status_code == 404


def test_levels_function_needs_membership(
    people: People, crew: dict[str, Any], app_engine: Engine
) -> None:
    people.client.put("/v1/me/level", json={"level": "advanced"}, headers=crew["sam"])
    outsider = people.new("Jordan")
    with committed_as(app_engine, people.user_id(outsider)) as conn:
        rows = conn.execute(
            text("SELECT * FROM app_group_levels(:g)"), {"g": crew["group_id"]}
        ).all()
    assert rows == []
    with committed_as(app_engine, people.user_id(crew["casey"])) as conn:
        levels = conn.execute(
            text("SELECT self_level FROM app_group_levels(:g)"), {"g": crew["group_id"]}
        ).scalars()
        assert list(levels) == ["advanced"]
