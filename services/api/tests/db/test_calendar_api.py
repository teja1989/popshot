"""The calendar (routes/calendar.py): a group's games and play nights between two times."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from tests.db.conftest import People, create
from tests.db.test_games_api import log
from tests.db.test_nights_api import plan

pytestmark = pytest.mark.db


def at(**delta: float) -> str:
    return (datetime.now(UTC) + timedelta(**delta)).isoformat()


def calendar(people: People, headers: dict[str, str], group_id: str, start: str, end: str) -> Any:
    return people.client.get(
        f"/v1/groups/{group_id}/calendar", params={"start": start, "end": end}, headers=headers
    )


def test_games_and_nights_in_the_range(people: People) -> None:
    casey = people.new("Casey")
    group_id = create(people, casey)["id"]
    me = people.client.get(f"/v1/groups/{group_id}/players", headers=casey).json()[0]["id"]
    guest = people.client.post(
        f"/v1/groups/{group_id}/players", json={"display_name": "Gary"}, headers=casey
    ).json()["id"]
    teams = {"format": "singles", "team_a": [me], "team_b": [guest]}
    inside = log(people, casey, group_id, played_at=at(days=-3), **teams).json()
    log(people, casey, group_id, played_at=at(days=-20), **teams)  # before the range
    night = plan(people, casey, group_id, starts_at=at(days=2)).json()[0]
    cancelled = plan(people, casey, group_id, starts_at=at(days=4)).json()[0]
    url = f"/v1/groups/{group_id}/nights/{cancelled['id']}/cancel"
    assert people.client.post(url, headers=casey).status_code == 200
    plan(people, casey, group_id, starts_at=at(days=20))  # after the range

    response = calendar(people, casey, group_id, at(days=-7), at(days=7))
    assert response.status_code == 200, response.text
    body = response.json()
    assert [g["id"] for g in body["games"]] == [inside["id"]]
    assert body["games"][0]["i_played"] is True
    # Cancelled nights are included, to show as cancelled; soonest first.
    assert [(n["id"], n["cancelled"]) for n in body["nights"]] == [
        (night["id"], False),
        (cancelled["id"], True),
    ]


def test_outsiders_cant_see_it(people: People) -> None:
    group_id = create(people, people.new("Casey"))["id"]
    response = calendar(people, people.new("Jordan"), group_id, at(days=-7), at(days=7))
    assert response.status_code == 404


@pytest.mark.parametrize(
    ("start", "end", "message"),
    [
        (at(days=1), at(days=-1), "after the start"),
        (at(days=-30), at(days=30), "six weeks"),
    ],
)
def test_the_range_is_checked(people: People, start: str, end: str, message: str) -> None:
    casey = people.new("Casey")
    group_id = create(people, casey)["id"]
    response = calendar(people, casey, group_id, start, end)
    assert response.status_code == 422
    assert message in response.json()["detail"]


def test_times_need_a_time_zone(people: People) -> None:
    casey = people.new("Casey")
    group_id = create(people, casey)["id"]
    response = calendar(people, casey, group_id, "2026-10-01T00:00:00", "2026-10-08T00:00:00")
    assert response.status_code == 422
