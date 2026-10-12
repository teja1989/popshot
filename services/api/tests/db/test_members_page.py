"""The members page's API: member details, guests, and the join-request push."""

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from popshot_api.main import create_app
from tests.conftest import make_settings
from tests.db.conftest import People, as_user, create
from tests.db.test_games_api import join_and_approve, log, players
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
    """Casey leads Lunch Dinkers with Sam. Guests Gary (in a game) and Gay (a typo)."""
    casey = people.new("Casey")
    gid = create(people, casey, name="Lunch Dinkers")["id"]
    sam = join_and_approve(people, casey, gid, "Sam")
    for name in ("Gary", "Gay"):
        added = people.client.post(
            f"/v1/groups/{gid}/players", json={"display_name": name}, headers=casey
        )
        assert added.status_code == 201, added.text
    ids = {name: p["id"] for name, p in players(people, casey, gid).items()}
    played = log(
        people,
        casey,
        gid,
        format="singles",
        team_a=[ids["Casey"]],
        team_b=[ids["Gary"]],
        games=[{"team_a": 11, "team_b": 7}],
    )
    assert played.status_code == 201, played.text
    return {"group_id": gid, "casey": casey, "sam": sam, "ids": ids}


def guests(people: People, who: Headers, gid: str) -> dict[str, dict[str, Any]]:
    response = people.client.get(f"/v1/groups/{gid}/guests", headers=who)
    assert response.status_code == 200, response.text
    return {g["display_name"]: g for g in response.json()}


def test_members_show_when_they_joined_and_last_played(
    people: People, crew: dict[str, Any]
) -> None:
    detail = people.client.get(f"/v1/groups/{crew['group_id']}", headers=crew["sam"]).json()
    by_name = {m["display_name"]: m for m in detail["members"]}
    assert by_name["Casey"]["last_played_at"] is not None
    assert by_name["Sam"]["last_played_at"] is None
    assert all(m["joined_at"] for m in detail["members"])


def test_everyone_sees_guests_and_their_games(people: People, crew: dict[str, Any]) -> None:
    seen = guests(people, crew["sam"], crew["group_id"])
    assert {name: g["games"] for name, g in seen.items()} == {"Gary": 1, "Gay": 0}
    outsider = people.new("Riley")
    assert (
        people.client.get(f"/v1/groups/{crew['group_id']}/guests", headers=outsider).status_code
        == 404
    )


def test_leads_rename_guests(people: People, crew: dict[str, Any]) -> None:
    gid = crew["group_id"]
    gay = guests(people, crew["casey"], gid)["Gay"]["id"]
    path = f"/v1/groups/{gid}/guests/{gay}"
    # Members can't.
    assert (
        people.client.patch(path, json={"display_name": "Gail"}, headers=crew["sam"]).status_code
        == 403
    )
    # Not to a name someone already has.
    taken = people.client.patch(path, json={"display_name": "sam"}, headers=crew["casey"])
    assert taken.status_code == 409
    renamed = people.client.patch(path, json={"display_name": "Gail"}, headers=crew["casey"])
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["display_name"] == "Gail"
    # A change of case of its own name is fine.
    same = people.client.patch(path, json={"display_name": "GAIL"}, headers=crew["casey"])
    assert same.status_code == 200
    # Not a member's player, through this route.
    sam_player = crew["ids"]["Sam"]
    assert (
        people.client.patch(
            f"/v1/groups/{gid}/guests/{sam_player}",
            json={"display_name": "X"},
            headers=crew["casey"],
        ).status_code
        == 404
    )


def test_only_unused_guests_can_be_removed(people: People, crew: dict[str, Any]) -> None:
    gid = crew["group_id"]
    seen = guests(people, crew["casey"], gid)
    gary, gay = seen["Gary"]["id"], seen["Gay"]["id"]
    assert (
        people.client.delete(f"/v1/groups/{gid}/guests/{gay}", headers=crew["sam"]).status_code
        == 403
    )
    kept = people.client.delete(f"/v1/groups/{gid}/guests/{gary}", headers=crew["casey"])
    assert kept.status_code == 409
    assert "stay" in kept.json()["detail"]
    gone = people.client.delete(f"/v1/groups/{gid}/guests/{gay}", headers=crew["casey"])
    assert gone.status_code == 204
    assert set(guests(people, crew["casey"], gid)) == {"Gary"}
    # Gary's game is untouched.
    games = people.client.get(f"/v1/groups/{gid}/matches", headers=crew["casey"]).json()
    assert len(games) == 1


def test_the_database_holds_the_rename_rules(
    people: People, crew: dict[str, Any], app_engine: Engine
) -> None:
    """Even straight to the database: members rename only their own player."""
    gid, ids = crew["group_id"], crew["ids"]
    sam = people.user_id(crew["sam"])
    rename = text("UPDATE players SET display_name = 'Hacked' WHERE id = :p")
    with as_user(app_engine, sam) as conn:
        assert conn.execute(rename, {"p": ids["Casey"]}).rowcount == 0
        assert conn.execute(rename, {"p": ids["Gary"]}).rowcount == 0
        assert conn.execute(rename, {"p": ids["Sam"]}).rowcount == 1
        # Nor delete players at all, or remove a guest through the function.
        assert (
            conn.execute(text("SELECT app_remove_guest(:p)"), {"p": ids["Gary"]}).scalar_one()
            == "not_found"
        )
    with as_user(app_engine, people.user_id(crew["casey"])) as conn:
        assert conn.execute(rename, {"p": ids["Gary"]}).rowcount == 1
        assert conn.execute(rename, {"p": ids["Sam"]}).rowcount == 0
    # Changing your own name still renames your player in each crew.
    people.client.patch("/v1/me", json={"display_name": "Samira"}, headers=crew["sam"])
    names = {p["display_name"] for p in players(people, crew["casey"], gid).values()}
    assert "Samira" in names


def test_leads_hear_once_when_someone_asks_to_join(
    people: People, crew: dict[str, Any], sender: RecordingSender, app_engine: Engine
) -> None:
    gid = crew["group_id"]
    casey_phone = device(people, crew["casey"])
    sam_phone = device(people, crew["sam"])
    link = people.client.post(
        f"/v1/groups/{gid}/invites", json={"max_uses": 5}, headers=crew["casey"]
    ).json()["token"]
    riley = people.new("Riley Stone")
    sender.sent.clear()
    joined = people.client.post("/v1/invites/join", json={"token": link}, headers=riley)
    assert joined.json()["status"] == "pending"
    # The lead hears; Sam, a member, doesn't.
    assert [endpoint for endpoint, _ in sender.sent] == [casey_phone]
    message = sender.sent[0][1]
    assert message.title == "Riley asked to join Lunch Dinkers"
    assert "Stone" not in message.payload()
    assert sam_phone not in [endpoint for endpoint, _ in sender.sent]
    # Tapping the link again: no second push.
    people.client.post("/v1/invites/join", json={"token": link}, headers=riley)
    assert len(sender.sent) == 1
    # Nothing to claim for someone who isn't waiting.
    with as_user(app_engine, people.user_id(crew["sam"])) as conn:
        assert (
            conn.execute(text("SELECT * FROM app_claim_join_request_push(:g)"), {"g": gid}).all()
            == []
        )


def test_leads_can_turn_join_request_pushes_off(
    people: People, crew: dict[str, Any], sender: RecordingSender
) -> None:
    gid = crew["group_id"]
    device(people, crew["casey"])
    muted = people.client.put(
        "/v1/me/notifications", json={"muted": ["requests"]}, headers=crew["casey"]
    )
    assert muted.status_code == 200, muted.text
    link = people.client.post(f"/v1/groups/{gid}/invites", json={}, headers=crew["casey"]).json()[
        "token"
    ]
    sender.sent.clear()
    people.client.post("/v1/invites/join", json={"token": link}, headers=people.new("Pat"))
    assert sender.sent == []


def test_someone_who_left_and_asks_again_is_announced_again(
    people: People, crew: dict[str, Any], sender: RecordingSender
) -> None:
    gid = crew["group_id"]
    device(people, crew["casey"])
    # Sam was let in once, then left; asking again is a new request.
    assert people.client.post(f"/v1/groups/{gid}/leave", headers=crew["sam"]).status_code == 204
    link = people.client.post(f"/v1/groups/{gid}/invites", json={}, headers=crew["casey"]).json()[
        "token"
    ]
    sender.sent.clear()
    again = people.client.post("/v1/invites/join", json={"token": link}, headers=crew["sam"])
    assert again.json()["status"] == "pending"
    assert len(sender.sent) == 1
