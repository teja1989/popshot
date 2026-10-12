"""Play nights, against the real database, with notifications recorded instead of sent."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from popshot_api.main import create_app
from tests.conftest import make_settings
from tests.db.conftest import People, committed_as, create
from tests.db.test_games_api import join_and_approve
from tests.db.test_notifications_api import RecordingSender, device
from tests.fakes import FakeTokenVerifier

pytestmark = pytest.mark.db

Headers = dict[str, str]


@pytest.fixture
def sender() -> RecordingSender:
    return RecordingSender()


@pytest.fixture
def people(app_engine: Engine, sender: RecordingSender) -> Iterator[People]:
    app = create_app(make_settings(), FakeTokenVerifier(), app_engine, push_sender=sender)
    with TestClient(app) as client:
        yield People(client, app.state.token_verifier)


@pytest.fixture
def crew(people: People) -> dict[str, Any]:
    """Casey (lead), Sam and Jo, each with notifications on."""
    casey = people.new("Casey")
    group_id = create(people, casey)["id"]
    sam = join_and_approve(people, casey, group_id, "Sam")
    jo = join_and_approve(people, casey, group_id, "Jo")
    devices = {name: device(people, h) for name, h in (("Casey", casey), ("Sam", sam), ("Jo", jo))}
    return {"group_id": group_id, "casey": casey, "sam": sam, "jo": jo, "devices": devices}


def soon(days: float = 2) -> str:
    return (datetime.now(UTC) + timedelta(days=days)).isoformat()


def plan(people: People, headers: Headers, group_id: str, **body: Any) -> Any:
    return people.client.post(
        f"/v1/groups/{group_id}/nights",
        json={"starts_at": soon(), "venue": "Riverside courts", **body},
        headers=headers,
    )


def rsvp(people: People, headers: Headers, night: dict[str, Any], answer: str) -> Any:
    return people.client.put(
        f"/v1/groups/{night['group_id']}/nights/{night['id']}/rsvp",
        json={"answer": answer},
        headers=headers,
    )


def names(people_list: list[dict[str, Any]]) -> list[str]:
    return [p["display_name"] for p in people_list]


def sent_to(sender: RecordingSender, crew: dict[str, Any]) -> set[str]:
    by_endpoint = {e: n for n, e in crew["devices"].items()}
    return {by_endpoint[e] for e, _ in sender.sent if e in by_endpoint}


def test_any_member_plans_a_night_and_the_crew_hears(
    people: People, crew: dict[str, Any], sender: RecordingSender
) -> None:
    made = plan(people, crew["sam"], crew["group_id"], note="Bring balls", spots=8)
    assert made.status_code == 201, made.text
    [night] = made.json()
    assert (night["venue"], night["note"], night["spots"]) == ("Riverside courts", "Bring balls", 8)
    assert names(night["going"]) == ["Sam"]
    assert night["my_answer"] == "in"
    assert night["can_edit"] is True
    assert night["open"] is True
    assert sent_to(sender, crew) == {"Casey", "Jo"}
    message = sender.sent[0][1]
    assert message.title == "Sam planned a meetup"
    assert message.url == f"/groups/{crew['group_id']}/nights/{night['id']}"


def test_weekly_nights(people: People, crew: dict[str, Any]) -> None:
    nights = plan(people, crew["casey"], crew["group_id"], weeks=3).json()
    assert len(nights) == 3
    starts = [datetime.fromisoformat(n["starts_at"]) for n in nights]
    assert starts[1] - starts[0] == starts[2] - starts[1] == timedelta(weeks=1)
    assert len({n["series_id"] for n in nights}) == 1
    assert nights[0]["series_id"] is not None
    listed = people.client.get(f"/v1/groups/{crew['group_id']}/nights", headers=crew["jo"]).json()
    assert [n["id"] for n in listed] == [n["id"] for n in nights]


@pytest.mark.parametrize(
    "body",
    [
        {"starts_at": (datetime.now(UTC) - timedelta(days=1)).isoformat()},
        {"starts_at": (datetime.now(UTC) + timedelta(days=400)).isoformat()},
        {"starts_at": "2026-12-01T18:00:00"},  # no time zone
        {"venue": ""},
        {"venue": "x" * 81},
        {"venue": "Court" + chr(0)},
        {"spots": 1},
        {"spots": 65},
        {"weeks": 13},
        {"owner": "me"},
    ],
)
def test_plans_are_checked(people: People, crew: dict[str, Any], body: dict[str, Any]) -> None:
    assert plan(people, crew["casey"], crew["group_id"], **body).status_code == 422


def test_outsiders_cant_see_or_plan(people: People, crew: dict[str, Any]) -> None:
    [night] = plan(people, crew["casey"], crew["group_id"]).json()
    outsider = people.new("Riley")
    assert plan(people, outsider, crew["group_id"]).status_code == 404
    gid = crew["group_id"]
    assert people.client.get(f"/v1/groups/{gid}/nights", headers=outsider).status_code == 404
    assert (
        people.client.get(f"/v1/groups/{gid}/nights/{night['id']}", headers=outsider).status_code
        == 404
    )
    assert rsvp(people, outsider, night, "in").status_code == 404


def test_waitlist_moves_up_when_someone_drops_out(
    people: People, crew: dict[str, Any], sender: RecordingSender
) -> None:
    [night] = plan(people, crew["casey"], crew["group_id"], spots=2).json()
    assert names(rsvp(people, crew["sam"], night, "in").json()["going"]) == ["Casey", "Sam"]
    jo_view = rsvp(people, crew["jo"], night, "in").json()
    assert names(jo_view["waitlist"]) == ["Jo"]
    assert jo_view["my_waitlist_position"] == 1

    sender.sent.clear()
    after = rsvp(people, crew["sam"], night, "out").json()
    assert names(after["going"]) == ["Casey", "Jo"]
    assert names(after["out"]) == ["Sam"]
    assert sent_to(sender, crew) == {"Jo"}
    assert sender.sent[0][1].title == "You're in: a spot opened up"

    # Sam comes back: the back of the queue. Saying "in" again keeps Jo's place.
    assert names(rsvp(people, crew["sam"], night, "in").json()["waitlist"]) == ["Sam"]
    assert names(rsvp(people, crew["jo"], night, "in").json()["going"]) == ["Casey", "Jo"]
    maybe = rsvp(people, crew["jo"], night, "maybe").json()
    assert names(maybe["maybe"]) == ["Jo"]
    assert names(maybe["going"]) == ["Casey", "Sam"]


def test_bad_answers(people: People, crew: dict[str, Any]) -> None:
    [night] = plan(people, crew["casey"], crew["group_id"]).json()
    assert rsvp(people, crew["sam"], night, "yes").status_code == 422


def test_only_the_planner_or_admins_change_a_night(
    people: People, crew: dict[str, Any], sender: RecordingSender
) -> None:
    [night] = plan(people, crew["sam"], crew["group_id"], spots=2).json()
    rsvp(people, crew["casey"], night, "in")
    rsvp(people, crew["jo"], night, "in")  # waitlisted
    url = f"/v1/groups/{crew['group_id']}/nights/{night['id']}"
    change = {"starts_at": soon(3), "venue": "Hilltop", "spots": 4}
    jo_view = people.client.get(url, headers=crew["jo"]).json()
    assert jo_view["can_edit"] is False
    assert people.client.patch(url, json=change, headers=crew["jo"]).status_code == 403

    sender.sent.clear()
    changed = people.client.patch(url, json=change, headers=crew["casey"])  # the lead
    assert changed.status_code == 200, changed.text
    assert changed.json()["venue"] == "Hilltop"
    assert names(changed.json()["going"]) == ["Sam", "Casey", "Jo"]
    assert sent_to(sender, crew) == {"Jo"}  # more spots moved Jo up


def test_cancelling_tells_whoever_was_coming(
    people: People, crew: dict[str, Any], sender: RecordingSender
) -> None:
    [night] = plan(people, crew["casey"], crew["group_id"]).json()
    rsvp(people, crew["sam"], night, "maybe")
    rsvp(people, crew["jo"], night, "out")
    sender.sent.clear()
    url = f"/v1/groups/{crew['group_id']}/nights/{night['id']}"
    cancelled = people.client.post(f"{url}/cancel", headers=crew["casey"])
    assert cancelled.status_code == 200
    assert cancelled.json()["cancelled"] is True
    assert cancelled.json()["open"] is False
    assert sent_to(sender, crew) == {"Sam"}  # Casey cancelled it; Jo said out
    assert rsvp(people, crew["jo"], night, "in").status_code == 409
    assert people.client.post(f"{url}/cancel", headers=crew["casey"]).status_code == 409
    # Still listed in the group (marked cancelled), but not among your next nights.
    listed = people.client.get(f"/v1/groups/{crew['group_id']}/nights", headers=crew["sam"]).json()
    assert [n["cancelled"] for n in listed] == [True]
    assert people.client.get("/v1/me/nights", headers=crew["sam"]).json() == []


def test_answers_close_after_the_start(
    people: People, crew: dict[str, Any], app_engine: Engine
) -> None:
    [night] = plan(people, crew["casey"], crew["group_id"]).json()
    with committed_as(app_engine, people.user_id(crew["casey"])) as conn:
        conn.execute(
            text("UPDATE play_nights SET starts_at = now() - interval '3 hours' WHERE id = :n"),
            {"n": night["id"]},
        )
    response = rsvp(people, crew["sam"], night, "in")
    assert response.status_code == 409
    assert "closed" in response.json()["detail"]


def test_my_next_nights_across_groups(people: People, crew: dict[str, Any]) -> None:
    other = create(people, crew["sam"], "Sunday Social")["id"]
    plan(people, crew["casey"], crew["group_id"], starts_at=soon(5))
    plan(people, crew["sam"], other, starts_at=soon(1))
    plan(people, crew["casey"], crew["group_id"], starts_at=soon(3), weeks=3)
    mine = people.client.get("/v1/me/nights", headers=crew["sam"]).json()
    assert [n["group_name"] for n in mine] == [
        "Sunday Social",
        "Tuesday Dinkers",
        "Tuesday Dinkers",
    ]
    assert len(mine) == 3
    # Jo isn't in Sunday Social.
    assert [
        n["group_name"] for n in people.client.get("/v1/me/nights", headers=crew["jo"]).json()
    ] == ["Tuesday Dinkers"] * 3


def test_people_who_leave_drop_off_the_list(people: People, crew: dict[str, Any]) -> None:
    [night] = plan(people, crew["casey"], crew["group_id"]).json()
    rsvp(people, crew["jo"], night, "in")
    people.client.post(f"/v1/groups/{crew['group_id']}/leave", headers=crew["jo"])
    view = people.client.get(
        f"/v1/groups/{crew['group_id']}/nights/{night['id']}", headers=crew["casey"]
    ).json()
    assert names(view["going"]) == ["Casey"]


def test_mute_play_nights(people: People, crew: dict[str, Any], sender: RecordingSender) -> None:
    people.client.put("/v1/me/notifications", json={"muted": ["play_nights"]}, headers=crew["jo"])
    plan(people, crew["casey"], crew["group_id"])
    assert sent_to(sender, crew) == {"Sam"}
