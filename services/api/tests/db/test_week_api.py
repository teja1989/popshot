"""Your week (popshot_api.week, routes/week.py): your own last 7 days, from your crews only."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from tests.db.conftest import People, create
from tests.db.test_games_api import add_guest, join_and_approve, log, players

pytestmark = pytest.mark.db

Headers = dict[str, str]


def week(people: People, who: Headers) -> dict[str, Any]:
    response = people.client.get("/v1/me/week", headers=who)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def ids(people: People, lead: Headers, gid: str) -> dict[str, str]:
    return {name.split()[0]: p["id"] for name, p in players(people, lead, gid).items()}


def test_your_week_counts_only_your_games_this_week(people: People) -> None:
    casey = people.new("Casey")
    gid = create(people, casey, "Week Crew")["id"]
    sam = join_and_approve(people, casey, gid, "Sam")
    add_guest(people, casey, gid, "Gary")
    who = ids(people, casey, gid)
    # Casey beats Gary twice (one close), and loses once to Sam.
    for score, opponent in (((11, 9), "Gary"), ((11, 3), "Gary"), ((6, 11), "Sam")):
        logged = log(
            people,
            casey,
            gid,
            format="singles",
            team_a=[who["Casey"]],
            team_b=[who[opponent]],
            games=[{"team_a": score[0], "team_b": score[1]}],
        )
        assert logged.status_code == 201, logged.text
    # Ten days ago: not this week.
    old = log(
        people,
        casey,
        gid,
        format="singles",
        team_a=[who["Casey"]],
        team_b=[who["Gary"]],
        played_at=(datetime.now(UTC) - timedelta(days=10)).isoformat(),
    )
    assert old.status_code == 201, old.text

    mine = week(people, casey)
    assert (mine["games"], mine["wins"], mine["close_games"]) == (3, 2, 1)
    assert mine["crews"] == ["Week Crew"]
    assert mine["headline"] == "3 games this week."
    # Sam played one game, and won it: Sam's week is Sam's own.
    theirs = week(people, sam)
    assert (theirs["games"], theirs["wins"]) == (1, 1)


def test_a_new_player_gets_a_quiet_week(people: People) -> None:
    body = week(people, people.new("Rowan"))
    assert body["games"] == 0
    assert body["headline"] == "A quiet week on court."
    assert body["top_partner"] is None


def test_other_crews_and_crews_you_left_dont_count(people: People) -> None:
    casey = people.new("Casey")
    mine = create(people, casey, "Mine")["id"]
    add_guest(people, casey, mine, "Gary")
    who = ids(people, casey, mine)
    log(people, casey, mine, format="singles", team_a=[who["Casey"]], team_b=[who["Gary"]])

    # A crew Casey isn't in, busy this week.
    stranger = people.new("Stranger")
    other = create(people, stranger, "Not Mine")["id"]
    add_guest(people, stranger, other, "Lou")
    them = ids(people, stranger, other)
    log(people, stranger, other, format="singles", team_a=[them["Stranger"]], team_b=[them["Lou"]])
    assert week(people, casey)["games"] == 1

    # A crew Casey played in this week, then left.
    left = create(people, stranger, "Left Behind")["id"]
    member = join_and_approve(people, stranger, left, "Pat")
    there = ids(people, stranger, left)
    log(people, stranger, left, format="singles", team_a=[there["Stranger"]], team_b=[there["Pat"]])
    assert week(people, member)["games"] == 1
    assert people.client.post(f"/v1/groups/{left}/leave", headers=member).status_code == 204
    assert week(people, member)["games"] == 0


def test_signed_out_is_refused(people: People) -> None:
    assert people.client.get("/v1/me/week").status_code == 401
