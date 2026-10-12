"""The push when a crew invites you (migration 0019), with a recording sender."""

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from popshot_api.main import create_app
from tests.conftest import make_settings
from tests.db.conftest import People, as_user, create
from tests.db.test_direct_invites_api import code_of, inbox, invite, person
from tests.db.test_games_api import join_and_approve
from tests.db.test_notifications_api import RecordingSender, device
from tests.fakes import FakeTokenVerifier

pytestmark = pytest.mark.db


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
    """Casey Long leads Dawn Dinkers with Sam; Robin has a phone with notifications on."""
    casey = people.new("Casey Long")
    group_id = create(people, casey, name="Dawn Dinkers")["id"]
    sam = join_and_approve(people, casey, group_id, "Sam")
    robin = people.new("Robin")
    phone = device(people, robin)
    found = person(people, casey, group_id, code_of(people, robin))
    assert found is not None
    return {
        "group_id": group_id,
        "casey": casey,
        "sam": sam,
        "robin": robin,
        "robin_id": found["user_id"],
        "phone": phone,
    }


def test_an_invite_pushes_once(
    people: People, crew: dict[str, Any], sender: RecordingSender
) -> None:
    sender.sent.clear()
    assert invite(people, crew["casey"], crew["group_id"], crew["robin_id"]).status_code == 201
    [(endpoint, message)] = sender.sent
    assert endpoint == crew["phone"]
    assert message.title == "Casey invited you to Dawn Dinkers"
    assert message.body == "Open Popshot to say yes or no."
    assert message.url == "/"
    # First name only on a lock screen.
    assert "Long" not in message.payload()
    # Sending it again: no second push.
    assert invite(people, crew["casey"], crew["group_id"], crew["robin_id"]).status_code == 201
    assert len(sender.sent) == 1


def test_no_push_after_a_decline_or_a_block(
    people: People, crew: dict[str, Any], sender: RecordingSender
) -> None:
    gid = crew["group_id"]
    invite(people, crew["casey"], gid, crew["robin_id"])
    [mine] = inbox(people, crew["robin"])
    people.client.post(
        f"/v1/me/invites/{mine['id']}", json={"answer": "block"}, headers=crew["robin"]
    )
    sender.sent.clear()
    assert invite(people, crew["casey"], gid, crew["robin_id"]).status_code == 201
    assert sender.sent == []


def test_no_push_when_invites_are_turned_off(
    people: People, crew: dict[str, Any], sender: RecordingSender
) -> None:
    muted = people.client.put(
        "/v1/me/notifications", json={"muted": ["invites"]}, headers=crew["robin"]
    )
    assert muted.status_code == 200, muted.text
    sender.sent.clear()
    assert invite(people, crew["casey"], crew["group_id"], crew["robin_id"]).status_code == 201
    assert sender.sent == []
    # The invite still waits on Home.
    assert len(inbox(people, crew["robin"])) == 1


def test_only_the_lead_who_invited_can_claim_the_push(
    people: People, crew: dict[str, Any], sender: RecordingSender, app_engine: Engine
) -> None:
    gid = crew["group_id"]
    with as_user(app_engine, people.user_id(crew["casey"])) as conn:
        # Nothing to claim before there's an invite.
        assert (
            conn.execute(
                text("SELECT * FROM app_claim_invite_push(:g, :u)"),
                {"g": gid, "u": crew["robin_id"]},
            ).all()
            == []
        )
    sender.sent.clear()
    invite(people, crew["casey"], gid, crew["robin_id"])
    assert len(sender.sent) == 1
    # Robin's devices can't be had again, by Casey or by anyone else.
    for who in ("casey", "sam"):
        with as_user(app_engine, people.user_id(crew[who])) as conn:
            assert (
                conn.execute(
                    text("SELECT * FROM app_claim_invite_push(:g, :u)"),
                    {"g": gid, "u": crew["robin_id"]},
                ).all()
                == []
            )


def test_another_lead_cant_claim_someone_elses_invite_push(
    people: People, crew: dict[str, Any], app_engine: Engine, owner_engine: Engine
) -> None:
    gid = crew["group_id"]
    sam_id = people.user_id(crew["sam"])
    promoted = people.client.patch(
        f"/v1/groups/{gid}/members/{sam_id}", json={"action": "make_co_lead"}, headers=crew["casey"]
    )
    assert promoted.status_code == 200, promoted.text
    invite(people, crew["casey"], gid, crew["robin_id"])
    # As if Casey's push hadn't gone out yet.
    with owner_engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE popshot_owner"))
        conn.execute(
            text("UPDATE direct_invites SET pushed_at = NULL WHERE group_id = :g"), {"g": gid}
        )
    claim = text("SELECT * FROM app_claim_invite_push(:g, :u)")
    with as_user(app_engine, sam_id) as conn:
        assert conn.execute(claim, {"g": gid, "u": crew["robin_id"]}).all() == []
    with as_user(app_engine, people.user_id(crew["casey"])) as conn:
        assert len(conn.execute(claim, {"g": gid, "u": crew["robin_id"]}).all()) == 1
