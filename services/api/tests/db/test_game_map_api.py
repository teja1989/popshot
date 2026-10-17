"""Your game map (routes/game_map.py, migration 0042): only your games, your goal, your eyes."""

from typing import Any

import pytest
from sqlalchemy import Engine, text

from popshot_api.game_map import MIN_GAMES
from tests.db.conftest import People, as_user, create
from tests.db.test_events_api import Lists, lists  # noqa: F401  (lists is a fixture)
from tests.db.test_features import owner
from tests.db.test_games_api import add_guest, join_and_approve, log, players

pytestmark = pytest.mark.db

Headers = dict[str, str]
MAP = "/v1/me/map"


@pytest.fixture
def crew(people: People, lists: Lists) -> dict[str, Any]:  # noqa: F811
    """Casey leads Map Crew with Sam, and guests Gary and Ivy. The map is on for the crew."""
    casey = people.new("Casey")
    gid = create(people, casey, "Map Crew")["id"]
    sam = join_and_approve(people, casey, gid, "Sam")
    for name in ("Gary", "Ivy"):
        assert add_guest(people, casey, gid, name).status_code == 201
    ids = {name.split()[0]: p["id"] for name, p in players(people, casey, gid).items()}
    lists.add("you.map", gid)
    return {"group_id": gid, "casey": casey, "sam": sam, "ids": ids}


def play(
    people: People, crew: dict[str, Any], a: list[str], b: list[str], score: tuple[int, int]
) -> None:
    response = log(
        people,
        crew["casey"],
        crew["group_id"],
        format="doubles" if len(a) == 2 else "singles",
        team_a=[crew["ids"][n] for n in a],
        team_b=[crew["ids"][n] for n in b],
        games=[{"team_a": score[0], "team_b": score[1]}],
    )
    assert response.status_code == 201, response.text


def game_map(people: People, who: Headers, **params: Any) -> dict[str, Any]:
    response = people.client.get(MAP, headers=who, params=params)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def test_off_until_switched_on(people: People, lists: Lists) -> None:  # noqa: F811
    casey = people.new("Casey")
    gid = create(people, casey)["id"]
    assert people.client.get(MAP, headers=casey).status_code == 404
    goal = people.client.put(f"{MAP}/goal", json={"weekly_games": 3}, headers=casey)
    assert goal.status_code == 404
    lists.add("you.map", gid)
    assert people.client.get(MAP, headers=casey).status_code == 200
    assert "you.map" in people.client.get("/v1/me/features", headers=casey).json()["you"]


def test_a_trail_of_weeks_with_the_box_for_now(people: People, crew: dict[str, Any]) -> None:
    for _ in range(MIN_GAMES):
        play(people, crew, ["Casey"], ["Gary"], (11, 2))
    body = game_map(people, crew["casey"])
    assert body["goal"] == 2
    assert body["goal_set"] is False
    assert body["min_games"] == MIN_GAMES
    *earlier, now = body["points"]
    assert len(earlier) == 5
    assert all(p["games"] == 0 and p["form"] is None and p["box"] is None for p in earlier)
    assert now["games"] == MIN_GAMES
    assert now["per_week"] == MIN_GAMES / 4
    # Won by more than crew points expected, fewer games a week than the goal.
    assert now["form"] > 0
    assert now["box"] == "sharp_play_more"
    assert len(game_map(people, crew["casey"], weeks=2)["points"]) == 2


def test_form_matches_the_crew_trend(people: People, crew: dict[str, Any]) -> None:
    for score in ((11, 2), (11, 9), (8, 11), (11, 4), (11, 6)):
        play(people, crew, ["Casey"], ["Gary"], score)
    now = game_map(people, crew["casey"])["points"][-1]
    (rating,) = people.client.get("/v1/me/ratings", headers=crew["casey"]).json()
    assert now["form"] == pytest.approx(rating["month_edge"], abs=0.001)


def test_your_goal_moves_the_line(people: People, crew: dict[str, Any]) -> None:
    for _ in range(MIN_GAMES):
        play(people, crew, ["Casey"], ["Gary"], (11, 2))
    saved = people.client.put(f"{MAP}/goal", json={"weekly_games": 1}, headers=crew["casey"])
    assert saved.status_code == 200, saved.text
    body = game_map(people, crew["casey"])
    assert (body["goal"], body["goal_set"]) == (1, True)
    assert body["points"][-1]["box"] == "in_the_groove"
    for bad in (0, 15, "two", None):
        response = people.client.put(
            f"{MAP}/goal", json={"weekly_games": bad}, headers=crew["casey"]
        )
        assert response.status_code == 422
    # Sam's goal is Sam's own.
    assert game_map(people, crew["sam"])["goal_set"] is False


def test_only_your_own_games_count(
    people: People,
    crew: dict[str, Any],
    lists: Lists,  # noqa: F811
) -> None:
    for _ in range(MIN_GAMES):
        play(people, crew, ["Casey"], ["Gary"], (11, 2))
    # Sam is in the crew but didn't play.
    assert all(p["games"] == 0 for p in game_map(people, crew["sam"])["points"])
    # Someone outside the crew, naming it, gets nothing from it.
    stranger = people.new("Riley")
    lists.add("you.map", create(people, stranger)["id"])
    body = game_map(people, stranger, crew=crew["group_id"])
    assert all(p["games"] == 0 for p in body["points"])
    assert [c["name"] for c in body["crews"]] == ["Tuesday Dinkers"]
    assert body["partners"] == []


def test_slices_by_partner_format_and_crew(people: People, crew: dict[str, Any]) -> None:
    for _ in range(MIN_GAMES):
        play(people, crew, ["Casey", "Ivy"], ["Sam", "Gary"], (11, 5))
    play(people, crew, ["Casey"], ["Gary"], (11, 9))
    body = game_map(people, crew["casey"])
    assert body["points"][-1]["games"] == MIN_GAMES + 1
    assert [c["name"] for c in body["crews"]] == ["Map Crew"]
    (partner,) = body["partners"]
    assert partner["player"]["display_name"] == "Ivy"
    assert partner["games"] == MIN_GAMES
    with_ivy = game_map(people, crew["casey"], partner=partner["player"]["player_id"])
    assert with_ivy["points"][-1]["games"] == MIN_GAMES
    assert game_map(people, crew["casey"], format="singles")["points"][-1]["games"] == 1
    assert game_map(people, crew["casey"], format="doubles")["points"][-1]["games"] == MIN_GAMES
    other = "00000000-0000-4000-8000-000000000000"
    assert game_map(people, crew["casey"], crew=other)["points"][-1]["games"] == 0
    assert (
        people.client.get(MAP, headers=crew["casey"], params={"format": "mixed"}).status_code == 422
    )
    assert people.client.get(MAP, headers=crew["casey"], params={"weeks": 27}).status_code == 422


def test_nobody_reads_or_writes_anyone_elses_goal(
    people: People, crew: dict[str, Any], app_engine: Engine
) -> None:
    people.client.put(f"{MAP}/goal", json={"weekly_games": 4}, headers=crew["casey"])
    casey, sam = people.user_id(crew["casey"]), people.user_id(crew["sam"])
    with as_user(app_engine, sam) as conn:
        assert conn.execute(text("SELECT count(*) FROM play_goals")).scalar_one() == 0
        changed = conn.execute(
            text("UPDATE play_goals SET weekly_games = 9 WHERE user_id = :u"), {"u": casey}
        )
        assert changed.rowcount == 0
        with pytest.raises(Exception, match="row-level security"):
            conn.execute(
                text("INSERT INTO play_goals (user_id, weekly_games) VALUES (:u, 3)"), {"u": casey}
            )
    with as_user(app_engine, None) as conn:
        assert conn.execute(text("SELECT count(*) FROM play_goals")).scalar_one() == 0
    assert game_map(people, crew["casey"])["goal"] == 4


def test_the_goal_is_in_your_download_and_goes_with_your_account(
    people: People, crew: dict[str, Any], owner_engine: Engine
) -> None:
    people.client.put(f"{MAP}/goal", json={"weekly_games": 3}, headers=crew["casey"])
    export = people.client.get("/v1/me/export", headers=crew["casey"]).json()
    assert export["play_goal"]["weekly_games"] == 3
    casey = people.user_id(crew["casey"])
    with owner(owner_engine) as conn:
        conn.execute(text("UPDATE users SET deleted_at = now() WHERE id = :u"), {"u": casey})
    with owner(owner_engine) as conn:
        left = conn.execute(
            text("SELECT count(*) FROM play_goals WHERE user_id = :u"), {"u": casey}
        ).scalar_one()
    assert left == 0


def test_the_database_keeps_goals_between_1_and_14(
    people: People, crew: dict[str, Any], app_engine: Engine
) -> None:
    casey = people.user_id(crew["casey"])
    for bad in (0, 15):
        with (
            as_user(app_engine, casey) as conn,
            pytest.raises(Exception, match="check"),
        ):
            conn.execute(
                text("INSERT INTO play_goals (user_id, weekly_games) VALUES (:u, :n)"),
                {"u": casey, "n": bad},
            )
