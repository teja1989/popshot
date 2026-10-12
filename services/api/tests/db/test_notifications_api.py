"""Push notifications, against the real database, with a sender that records instead of
sending."""

from collections.abc import Iterable, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from popshot_api.main import create_app
from popshot_api.push import Message, PushSender, Subscription
from tests.conftest import make_settings
from tests.db.conftest import People, as_user, create
from tests.db.test_games_api import join_and_approve, log, players
from tests.fakes import FakeTokenVerifier
from tests.test_push import browser_keys, pem_key

pytestmark = pytest.mark.db

Headers = dict[str, str]


class RecordingSender(PushSender):
    def __init__(self) -> None:
        super().__init__(pem_key(), "https://example.com")
        self.sent: list[tuple[str, Message]] = []
        self.gone: set[str] = set()

    def send(self, subscriptions: Iterable[Subscription], message: Message) -> list[str]:
        subs = list(subscriptions)
        self.sent.extend((s.endpoint, message) for s in subs)
        return [s.endpoint for s in subs if s.endpoint in self.gone]


@pytest.fixture
def sender() -> RecordingSender:
    return RecordingSender()


@pytest.fixture
def crew(app_engine: Engine, sender: RecordingSender) -> Iterator[People]:
    app = create_app(make_settings(), FakeTokenVerifier(), app_engine, push_sender=sender)
    with TestClient(app) as client:
        yield People(client, app.state.token_verifier)


_counter = iter(range(10_000))


def device(people: People, headers: Headers, endpoint: str | None = None) -> str:
    endpoint = endpoint or f"https://fcm.googleapis.com/fcm/send/device-{next(_counter)}"
    p256dh, auth = browser_keys()
    response = people.client.post(
        "/v1/me/push-subscriptions",
        json={
            "endpoint": endpoint,
            "expirationTime": None,
            "keys": {"p256dh": p256dh, "auth": auth},
        },
        headers=headers,
    )
    assert response.status_code == 204, response.text
    return endpoint


def settings(people: People, headers: Headers) -> dict[str, Any]:
    body: dict[str, Any] = people.client.get("/v1/me/notifications", headers=headers).json()
    return body


def test_config_gives_the_public_key(crew: People, sender: RecordingSender, people: People) -> None:
    assert crew.client.get("/v1/push/config").json() == {"public_key": sender.public_key}
    # Without a key configured, push is off.
    assert people.client.get("/v1/push/config").json() == {"public_key": None}


@pytest.mark.parametrize(
    "endpoint",
    ["https://evil.example.com/x", "http://fcm.googleapis.com/x", "https://169.254.169.254/x"],
)
def test_only_push_services_are_accepted(crew: People, endpoint: str) -> None:
    p256dh, auth = browser_keys()
    response = crew.client.post(
        "/v1/me/push-subscriptions",
        json={"endpoint": endpoint, "keys": {"p256dh": p256dh, "auth": auth}},
        headers=crew.new("Casey"),
    )
    assert response.status_code == 422


def test_malformed_keys_are_refused(crew: People) -> None:
    response = crew.client.post(
        "/v1/me/push-subscriptions",
        json={
            "endpoint": "https://fcm.googleapis.com/fcm/send/x",
            "keys": {"p256dh": "no spaces!", "auth": "x"},
        },
        headers=crew.new("Casey"),
    )
    assert response.status_code == 422


def test_a_device_belongs_to_whoever_turned_it_on_last(crew: People) -> None:
    casey, sam = crew.new("Casey"), crew.new("Sam")
    endpoint = device(crew, casey)
    assert settings(crew, casey)["devices"] == 1
    device(crew, sam, endpoint)
    assert settings(crew, casey)["devices"] == 0
    assert settings(crew, sam)["devices"] == 1
    # Removing only ever removes your own.
    crew.client.post("/v1/me/push-subscriptions/remove", json={"endpoint": endpoint}, headers=casey)
    assert settings(crew, sam)["devices"] == 1
    crew.client.post("/v1/me/push-subscriptions/remove", json={"endpoint": endpoint}, headers=sam)
    assert settings(crew, sam)["devices"] == 0


def test_muting_a_category(crew: People) -> None:
    casey = crew.new("Casey")
    assert settings(crew, casey) == {
        "categories": ["play_nights", "recaps", "games"],
        "muted": [],
        "devices": 0,
    }
    muted = crew.client.put("/v1/me/notifications", json={"muted": ["games"]}, headers=casey)
    assert muted.json()["muted"] == ["games"]
    assert (
        crew.client.put("/v1/me/notifications", json={"muted": ["spam"]}, headers=casey).status_code
        == 422
    )


def test_logging_a_game_tells_the_members_who_played(crew: People, sender: RecordingSender) -> None:
    casey = crew.new("Casey")
    group_id = create(crew, casey)["id"]
    sam = join_and_approve(crew, casey, group_id, "Sam")
    jo = join_and_approve(crew, casey, group_id, "Jo")
    crew.client.post(f"/v1/groups/{group_id}/players", json={"display_name": "Gary"}, headers=casey)
    ids = {n: p["id"] for n, p in players(crew, casey, group_id).items()}
    casey_device, sam_device, jo_device = device(crew, casey), device(crew, sam), device(crew, jo)

    game = log(
        crew,
        casey,
        group_id,
        format="doubles",
        team_a=[ids["Casey"], ids["Gary"]],
        team_b=[ids["Sam"], ids["Jo"]],
        games=[{"team_a": 11, "team_b": 4}],
    )
    assert game.status_code == 201, game.text
    to = {endpoint for endpoint, _ in sender.sent}
    # Sam and Jo played; Casey logged it; Gary is a guest.
    assert to == {sam_device, jo_device}
    assert casey_device not in to
    message = sender.sent[0][1]
    assert message.title == "Casey logged a game you played"
    assert "11" not in message.title + message.body  # no scores on lock screens
    assert message.url == "/games"

    # Jo mutes games; Sam's device has gone away and is forgotten.
    crew.client.put("/v1/me/notifications", json={"muted": ["games"]}, headers=jo)
    sender.gone.add(sam_device)
    sender.sent.clear()
    log(
        crew,
        casey,
        group_id,
        format="doubles",
        team_a=[ids["Casey"], ids["Gary"]],
        team_b=[ids["Sam"], ids["Jo"]],
        games=[{"team_a": 11, "team_b": 9}],
    )
    assert {endpoint for endpoint, _ in sender.sent} == {sam_device}
    assert settings(crew, sam)["devices"] == 0


def test_targets_are_limited_to_your_crew(crew: People, app_engine: Engine) -> None:
    casey, stranger = crew.new("Casey"), crew.new("Riley")
    create(crew, casey)
    device(crew, stranger)
    with as_user(app_engine, crew.user_id(casey)) as conn:
        rows = conn.execute(
            text("SELECT * FROM app_push_targets(CAST(:u AS uuid[]), 'games')"),
            {"u": [str(crew.user_id(stranger)), str(crew.user_id(casey))]},
        ).all()
    assert rows == []


def test_subscriptions_are_private(crew: People, app_engine: Engine) -> None:
    casey, sam = crew.new("Casey"), crew.new("Sam")
    device(crew, casey)
    with as_user(app_engine, crew.user_id(sam)) as conn:
        assert conn.execute(text("SELECT count(*) FROM push_subscriptions")).scalar_one() == 0
        assert conn.execute(text("DELETE FROM push_subscriptions")).rowcount == 0
        assert conn.execute(text("SELECT count(*) FROM notification_settings")).scalar_one() == 0


def test_send_a_test(crew: People, sender: RecordingSender, people: People) -> None:
    casey = crew.new("Casey")
    assert crew.client.post("/v1/me/push-test", headers=casey).status_code == 409
    mine = device(crew, casey)
    assert crew.client.post("/v1/me/push-test", headers=casey).status_code == 202
    assert [e for e, _ in sender.sent] == [mine]
    # Push not set up on the server.
    assert people.client.post("/v1/me/push-test", headers=people.new("Sam")).status_code == 409
