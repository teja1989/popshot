"""Head-to-head stats and crew highlights, against the real database."""

from typing import Any

import pytest
from sqlalchemy import Engine, text

from popshot_api.stats import MIN_PAIRING
from tests.db.conftest import People, committed_as
from tests.db.test_board_api import crew, singles  # noqa: F401  (crew is a fixture)
from tests.db.test_games_api import log, players

pytestmark = pytest.mark.db

Headers = dict[str, str]


def my_stats(people: People, headers: Headers, group_id: str) -> dict[str, Any]:
    response = people.client.get(f"/v1/groups/{group_id}/stats/me", headers=headers)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def highlights(people: People, headers: Headers, group_id: str) -> dict[str, Any]:
    response = people.client.get(f"/v1/groups/{group_id}/highlights", headers=headers)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def test_no_games_yet(people: People, crew: dict[str, Any]) -> None:  # noqa: F811
    s = my_stats(people, crew["sam"], crew["group_id"])
    assert (s["matches"], s["current_streak"], s["nemesis"], s["head_to_head"]) == (
        0,
        None,
        None,
        [],
    )
    assert s["min_pairing"] == MIN_PAIRING
    h = highlights(people, crew["sam"], crew["group_id"])
    assert (h["longest_win_streak"], h["most_games"], h["biggest_upset"]) == (None, None, None)
    assert h["window_days"] == 30


def test_nemesis_streaks_skunks_and_close_games(people: People, crew: dict[str, Any]) -> None:  # noqa: F811
    # Casey loses to Gary five times, then wins twice: 11-2 (skunk) and 12-10 (close).
    for _ in range(MIN_PAIRING):
        singles(people, crew, "Casey", "Gary", (6, 11))
    singles(people, crew, "Casey", "Gary", (11, 2))
    singles(people, crew, "Casey", "Gary", (12, 10))

    s = my_stats(people, crew["casey"], crew["group_id"])
    assert (s["matches"], s["wins"]) == (7, 2)
    assert s["current_streak"] == {"result": "W", "length": 2}
    assert s["longest_win_streak"] == 2
    assert (s["skunks_given"], s["skunks_taken"], s["close_won"], s["close_lost"]) == (1, 0, 1, 0)
    assert s["nemesis"]["player"]["display_name"] == "Gary"
    assert s["nemesis"]["player"]["is_guest"] is True
    assert (s["nemesis"]["played"], s["nemesis"]["won"]) == (7, 2)
    assert [r["player"]["display_name"] for r in s["head_to_head"]] == ["Gary"]
    # After five losses Casey is the underdog, so both wins are upsets.
    assert s["upset_wins"] == 2
    assert s["biggest_upset"]["winners"][0]["display_name"] == "Casey"
    assert s["biggest_upset"]["gap"] > 0

    # Sam has played nobody.
    assert my_stats(people, crew["sam"], crew["group_id"])["matches"] == 0


def test_best_partner(people: People, crew: dict[str, Any]) -> None:  # noqa: F811
    ids = crew["ids"]
    people.client.post(
        f"/v1/groups/{crew['group_id']}/players",
        json={"display_name": "Jo"},
        headers=crew["casey"],
    )
    jo = players(people, crew["casey"], crew["group_id"])["Jo"]["id"]
    for _ in range(MIN_PAIRING):
        response = log(
            people,
            crew["casey"],
            crew["group_id"],
            format="doubles",
            team_a=[ids["Casey"], ids["Sam"]],
            team_b=[ids["Gary"], jo],
            games=[{"team_a": 11, "team_b": 7}],
        )
        assert response.status_code == 201, response.text
    s = my_stats(people, crew["sam"], crew["group_id"])
    assert s["best_partner"]["player"]["display_name"] == "Casey"
    assert (s["best_partner"]["played"], s["best_partner"]["won"]) == (MIN_PAIRING, MIN_PAIRING)
    assert s["nemesis"] is None


def test_highlights(people: People, crew: dict[str, Any], app_engine: Engine) -> None:  # noqa: F811
    old = [singles(people, crew, "Sam", "Gary", (11, 4)) for _ in range(3)]
    with committed_as(app_engine, people.user_id(crew["casey"])) as conn:
        conn.execute(
            text("UPDATE matches SET played_at = now() - interval '40 days' WHERE id = ANY(:ids)"),
            {"ids": old},
        )
    singles(people, crew, "Casey", "Gary", (11, 8))
    singles(people, crew, "Casey", "Gary", (11, 8))
    h = highlights(people, crew["casey"], crew["group_id"])
    # Sam's three straight wins are older than 30 days but still the longest streak.
    assert h["longest_win_streak"] == {
        "player": {"player_id": crew["ids"]["Sam"], "display_name": "Sam", "is_guest": False},
        "length": 3,
    }
    # Only the last 30 days count for games: Casey and Gary have 2 each.
    assert h["most_games"]["matches"] == 2
    assert h["most_games"]["player"]["display_name"] in {"Casey", "Gary"}
    # Gary lost three times to Sam, so Casey was the favourite both times: no upset.
    assert h["biggest_upset"] is None

    # Sam leaves: the streak goes to someone still in the group.
    people.client.patch(
        f"/v1/groups/{crew['group_id']}/members/{people.user_id(crew['sam'])}",
        json={"action": "remove"},
        headers=crew["casey"],
    )
    h = highlights(people, crew["casey"], crew["group_id"])
    assert h["longest_win_streak"]["player"]["display_name"] == "Casey"
    assert h["longest_win_streak"]["length"] == 2


def test_outsiders_get_nothing(people: People, crew: dict[str, Any]) -> None:  # noqa: F811
    outsider = people.new("Jordan")
    for path in ("stats/me", "highlights"):
        response = people.client.get(f"/v1/groups/{crew['group_id']}/{path}", headers=outsider)
        assert response.status_code == 404
