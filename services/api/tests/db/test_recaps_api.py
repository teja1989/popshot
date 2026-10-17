"""Recaps (routes/recaps.py), against the real database."""

from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import Engine, event, text

from popshot_api.recap import MIN_GAMES, day_key
from tests.db.conftest import People, committed_as
from tests.db.test_board_api import crew, singles  # noqa: F401  (crew is a fixture)
from tests.db.test_nights_api import plan

pytestmark = pytest.mark.db

Headers = dict[str, str]


def recap_key(app_engine: Engine, user_id: Any, group_id: str, match_id: str) -> UUID:
    """The key of the day `match_id` was played on, in the crew's time zone."""
    with committed_as(app_engine, user_id) as conn:
        row = conn.execute(
            text(
                "SELECT (m.played_at AT TIME ZONE g.time_zone)::date AS day FROM matches m "
                "JOIN groups g ON g.id = m.group_id WHERE m.id = :id"
            ),
            {"id": match_id},
        ).one()
    return day_key(UUID(group_id), row.day)


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
    singles(people, crew, "Sam", "Gary", (12, 10))  # won by two, past game point

    # Last month's day had one game: history, but no recap of its own.
    listed = get(people, crew["sam"], f"/v1/groups/{group_id}/recaps")
    assert [r["games"] for r in listed] == [3]
    newest = listed[0]
    assert newest["venue"] == "Riverside courts"
    assert newest["headline"]

    recap = get(people, crew["sam"], f"/v1/groups/{group_id}/recaps/{newest['key']}")
    assert [p["display_name"] for p in recap["newcomers"]] == ["Sam"]
    awards = {a["kind"]: a for a in recap["awards"]}
    assert [p["display_name"] for p in awards["close_call"]["players"]] == ["Casey", "Sam"]
    assert awards["close_call"]["value"] == 2
    # Singles only: no partners to win with or to welcome.
    assert "great_partner" not in awards
    assert "welcome_wagon" not in awards
    assert {p["player"]["display_name"]: p["games"] for p in recap["played"]} == {
        "Gary": 3,
        "Casey": 1,
        "Sam": 2,
    }
    # The first-timer is welcomed first.
    assert "Sam" in recap["lines"][0]
    assert len(recap["match_ids"]) == 3
    # Last month's day, too small for a recap, can't be opened either.
    old_day = recap_key(app_engine, casey_id, group_id, old)
    response = people.client.get(f"/v1/groups/{group_id}/recaps/{old_day}", headers=crew["sam"])
    assert response.status_code == 404


def test_recaps_are_for_members_only(people: People, crew: dict[str, Any]) -> None:  # noqa: F811
    for _ in range(MIN_GAMES):
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


def test_listing_recaps_takes_the_same_queries_however_many_days(
    people: People,
    crew: dict[str, Any],  # noqa: F811
    app_engine: Engine,
) -> None:
    group_id = crew["group_id"]
    path = f"/v1/groups/{group_id}/recaps"

    def queries() -> int:
        seen: list[str] = []

        def count(*_: Any) -> None:
            seen.append("query")

        event.listen(app_engine, "before_cursor_execute", count)
        try:
            get(people, crew["casey"], path)
        finally:
            event.remove(app_engine, "before_cursor_execute", count)
        return len(seen)

    def play_a_day(days_ago: int) -> None:
        ids = [singles(people, crew, "Casey", "Gary", (11, 3)) for _ in range(MIN_GAMES)]
        with committed_as(app_engine, people.user_id(crew["casey"])) as conn:
            conn.execute(
                text(
                    "UPDATE matches SET played_at = played_at - make_interval(days => :d) "
                    "WHERE id = ANY(CAST(:ids AS uuid[]))"
                ),
                {"d": days_ago, "ids": ids},
            )

    play_a_day(3)
    one_day = queries()
    for days_ago in (2, 1, 0):
        play_a_day(days_ago)
    assert len(get(people, crew["casey"], path)) == 4
    assert queries() == one_day
