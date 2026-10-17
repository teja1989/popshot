"""Shared recap links (routes/shares.py), against the real database."""

import hashlib
import secrets
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from popshot_api.main import create_app
from popshot_api.recap import MIN_GAMES
from popshot_api.routes.shares import MAX_LIVE_SHARES
from tests.conftest import make_settings
from tests.db.conftest import People, as_user, committed_as, create, sqlstate_of
from tests.db.test_ai_recaps_api import FakeWriter, age
from tests.db.test_games_api import join_and_approve, log, players
from tests.db.test_nights_api import plan
from tests.fakes import FakeTokenVerifier

pytestmark = pytest.mark.db

Headers = dict[str, str]
CHECK_VIOLATION = "23514"
DEAD = "This recap link isn't available any more."


@pytest.fixture
def writer() -> FakeWriter:
    return FakeWriter()


@pytest.fixture
def people(app_engine: Engine, writer: FakeWriter) -> Iterator[People]:
    app = create_app(make_settings(), FakeTokenVerifier(), app_engine, recap_writer=writer)
    with TestClient(app) as client:
        yield People(client, app.state.token_verifier)


@pytest.fixture
def crew(people: People) -> dict[str, Any]:
    """Casey Long (lead), Sam Field and Jo, plus guest Gary."""
    casey = people.new("Casey Long")
    group_id = create(people, casey, name="Lunch Dinkers")["id"]
    sam = join_and_approve(people, casey, group_id, "Sam Field")
    jo = join_and_approve(people, casey, group_id, "Jo")
    people.client.post(
        f"/v1/groups/{group_id}/players", json={"display_name": "Gary"}, headers=casey
    )
    ids = {name.split()[0]: p["id"] for name, p in players(people, casey, group_id).items()}
    return {"group_id": group_id, "casey": casey, "sam": sam, "jo": jo, "ids": ids}


def doubles(people: People, crew: dict[str, Any], a: list[str], b: list[str], score: Any) -> str:
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
    match_id: str = response.json()["id"]
    return match_id


def day_of(people: People, crew: dict[str, Any], a: list[str], b: list[str], score: Any) -> None:
    """The same game MIN_GAMES times: a day with a recap."""
    for _ in range(MIN_GAMES):
        doubles(people, crew, a, b, score)


def at_venue(
    people: People, crew: dict[str, Any], app_engine: Engine, venue: str, ago: str = "30 minutes"
) -> None:
    """A meetup at `venue` that started `ago`, so games logged now are at it."""
    night = plan(people, crew["casey"], crew["group_id"], venue=venue).json()[0]
    with committed_as(app_engine, people.user_id(crew["casey"])) as conn:
        conn.execute(
            text("UPDATE play_nights SET starts_at = now() - CAST(:ago AS interval) WHERE id = :i"),
            {"i": night["id"], "ago": ago},
        )


def key_of(people: People, crew: dict[str, Any]) -> str:
    listed = people.client.get(f"/v1/groups/{crew['group_id']}/recaps", headers=crew["sam"]).json()
    key: str = listed[0]["key"]
    return key


def share(people: People, crew: dict[str, Any], key: str, who: str = "sam") -> Any:
    return people.client.post(
        f"/v1/groups/{crew['group_id']}/recaps/{key}/share", headers=crew[who]
    )


def shared(people: People, token: str) -> Any:
    # No Authorization header: anyone with the link.
    return people.client.post("/v1/public/recap", json={"token": token})


def card(people: People, token: str) -> dict[str, Any]:
    response = shared(people, token)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def turn_off(people: People, crew: dict[str, Any], key: str, who: str) -> int:
    response = people.client.delete(
        f"/v1/groups/{crew['group_id']}/recaps/{key}/share", headers=crew[who]
    )
    assert response.status_code == 200, response.text
    turned_off: int = response.json()["turned_off"]
    return turned_off


def test_anyone_with_the_link_sees_the_card(
    people: People, crew: dict[str, Any], app_engine: Engine
) -> None:
    at_venue(people, crew, app_engine, "12 Elm Street")
    day_of(people, crew, ["Casey", "Sam"], ["Jo", "Gary"], (11, 9))
    key = key_of(people, crew)

    response = share(people, crew, key)
    assert response.status_code == 201, response.text
    token = response.json()["token"]
    assert len(token) == 43

    body = card(people, token)
    assert body["crew"] == "Lunch Dinkers"
    assert body["games"] == MIN_GAMES
    # First names only, with the scores.
    assert len(body["matches"]) == MIN_GAMES
    for game in body["matches"]:
        assert sorted(game["team_a"]) == ["Casey", "Sam"]
        assert sorted(game["team_b"]) == ["Gary", "Jo"]
        assert game["games"] == [[11, 9]]
    assert sorted(p["name"] for p in body["played"]) == ["Casey", "Gary", "Jo", "Sam"]
    flat = repr(body)
    # No surnames, ids, emails or venue (it could be someone's home).
    for leak in ("Long", "Field", "@", "Elm", *crew["ids"].values(), crew["group_id"], key):
        assert leak not in flat


def test_a_link_works_only_for_its_outing(
    people: People, crew: dict[str, Any], app_engine: Engine
) -> None:
    day_of(people, crew, ["Casey"], ["Gary"], (11, 3))
    age(app_engine, people, crew, "2 days")
    day_of(people, crew, ["Sam"], ["Jo"], (11, 7))
    listed = people.client.get(f"/v1/groups/{crew['group_id']}/recaps", headers=crew["sam"])
    older = listed.json()[1]["key"]
    body = card(people, share(people, crew, older).json()["token"])
    assert [m["games"] for m in body["matches"]] == [[[11, 3]]] * MIN_GAMES


def test_bad_and_unknown_links_look_the_same(people: People) -> None:
    for token in ("", "short", "x" * 43, secrets.token_urlsafe(32), "../" + "a" * 40):
        response = shared(people, token)
        assert response.status_code == 404
        assert response.json()["detail"] == DEAD
    assert people.client.post("/v1/public/recap", json={"token": "a" * 65}).status_code == 422
    assert people.client.post("/v1/public/recap", json={}).status_code == 422


def test_only_members_share_and_only_real_outings(people: People, crew: dict[str, Any]) -> None:
    day_of(people, crew, ["Casey"], ["Gary"], (11, 3))
    key = key_of(people, crew)
    outsider = people.new("Riley")
    gid = crew["group_id"]
    for path in (f"/v1/groups/{gid}/recaps/{key}/share",):
        assert people.client.post(path, headers=outsider).status_code == 404
        assert people.client.get(path, headers=outsider).status_code == 404
        assert people.client.delete(path, headers=outsider).status_code == 404
    # A key that isn't an outing of this crew.
    other = create(people, outsider)["id"]
    assert (
        people.client.post(f"/v1/groups/{other}/recaps/{key}/share", headers=outsider).status_code
        == 404
    )
    unknown = "00000000-0000-4000-8000-000000000000"
    assert share(people, crew, unknown).status_code == 404


def test_who_can_turn_links_off(people: People, crew: dict[str, Any]) -> None:
    day_of(people, crew, ["Casey"], ["Gary"], (11, 3))
    key = key_of(people, crew)
    sams = share(people, crew, key, "sam").json()["token"]
    jos = share(people, crew, key, "jo").json()["token"]
    status = people.client.get(
        f"/v1/groups/{crew['group_id']}/recaps/{key}/share", headers=crew["sam"]
    ).json()
    assert status == {"live": 2, "yours_to_turn_off": 1}

    # Sam can't turn off Jo's link, only Sam's own.
    assert turn_off(people, crew, key, "sam") == 1
    assert shared(people, sams).status_code == 404
    assert shared(people, jos).status_code == 200
    # The lead can turn off anyone's.
    assert turn_off(people, crew, key, "casey") == 1
    assert shared(people, jos).status_code == 404
    assert turn_off(people, crew, key, "casey") == 0


def test_expired_links_and_deleted_crews_are_gone(
    people: People, crew: dict[str, Any], app_engine: Engine
) -> None:
    day_of(people, crew, ["Casey"], ["Gary"], (11, 3))
    key = key_of(people, crew)
    token = secrets.token_urlsafe(32)
    with committed_as(app_engine, people.user_id(crew["sam"])) as conn:
        conn.execute(
            text(
                "INSERT INTO recap_shares "
                "(token_hash, group_id, outing_key, created_by, created_at, expires_at) "
                "VALUES (:h, :g, :k, :u, now() - interval '31 days', now() - interval '1 day')"
            ),
            {
                "h": hashlib.sha256(token.encode()).digest(),
                "g": crew["group_id"],
                "k": key,
                "u": people.user_id(crew["sam"]),
            },
        )
    assert shared(people, token).status_code == 404

    live = share(people, crew, key).json()["token"]
    assert shared(people, live).status_code == 200
    gone = people.client.delete(f"/v1/groups/{crew['group_id']}", headers=crew["casey"])
    assert gone.status_code == 204
    assert shared(people, live).status_code == 404


def test_links_cannot_outlast_thirty_days(
    people: People, crew: dict[str, Any], app_engine: Engine
) -> None:
    day_of(people, crew, ["Casey"], ["Gary"], (11, 3))
    key = key_of(people, crew)
    sam = people.user_id(crew["sam"])
    sql = (
        "INSERT INTO recap_shares (token_hash, group_id, outing_key, created_by, expires_at) "
        "VALUES (:h, :g, :k, :u, now() + interval '31 days')"
    )
    params = {"h": secrets.token_bytes(32), "g": crew["group_id"], "k": key, "u": sam}
    with as_user(app_engine, sam) as conn:
        assert sqlstate_of(conn, sql, params) == CHECK_VIOLATION
    created = share(people, crew, key).json()["expires_at"]
    days = datetime.fromisoformat(created) - datetime.now(UTC)
    assert timedelta(days=29, hours=23) < days <= timedelta(days=30)


def test_people_can_stay_off_shared_cards(people: People, crew: dict[str, Any]) -> None:
    response = people.client.put(
        "/v1/me/shared-cards", json={"hide_on_shared_cards": True}, headers=crew["sam"]
    )
    assert response.status_code == 200, response.text
    assert response.json()["hide_on_shared_cards"] is True
    assert people.client.get("/v1/me", headers=crew["jo"]).json()["hide_on_shared_cards"] is False

    # Sam and Jo play their first game: both are newcomers. Sam wins by two.
    day_of(people, crew, ["Sam"], ["Jo"], (11, 9))
    key = key_of(people, crew)
    body = card(people, share(people, crew, key, "jo").json()["token"])
    assert "Sam" not in repr(body)
    assert body["matches"][0]["team_a"] == ["Crew member"]
    assert body["matches"][0]["team_b"] == ["Jo"]
    assert body["newcomers"] == {"names": ["Jo"], "more": 1}
    awards = {a["kind"]: a for a in body["awards"]}
    assert awards["close_call"]["names"] == []
    assert awards["close_call"]["more"] == 1
    # Inside the app, Sam is still named.
    inside = people.client.get(
        f"/v1/groups/{crew['group_id']}/recaps/{key}", headers=crew["jo"]
    ).json()
    assert "Sam" in repr(inside)


def test_ai_words_are_used_only_if_they_name_nobody_hidden(
    people: People, crew: dict[str, Any], writer: FakeWriter, app_engine: Engine
) -> None:
    day_of(people, crew, ["Sam"], ["Jo"], (11, 4))
    age(app_engine, people, crew, "2 hours")
    key = key_of(people, crew)
    writer.reply = {"headline": "Paddles up, crew!", "lines": ["Sam and Jo kept rallying."]}
    # Opening the recap in the app writes the words.
    people.client.get(f"/v1/groups/{crew['group_id']}/recaps/{key}", headers=crew["jo"])
    token = share(people, crew, key).json()["token"]

    body = card(people, token)
    assert body["written_by"] == "ai"
    assert body["lines"] == ["Sam and Jo kept rallying."]

    people.client.put(
        "/v1/me/shared-cards", json={"hide_on_shared_cards": True}, headers=crew["sam"]
    )
    body = card(people, token)
    assert body["written_by"] == "popshot"
    assert "Sam" not in repr(body)
    # The card never asks the AI itself.
    assert len(writer.calls) == 1


def test_ai_words_naming_the_venue_are_not_shared(
    people: People, crew: dict[str, Any], writer: FakeWriter, app_engine: Engine
) -> None:
    at_venue(people, crew, app_engine, "Elm Street", "150 minutes")
    day_of(people, crew, ["Sam"], ["Jo"], (11, 4))
    age(app_engine, people, crew, "2 hours")
    key = key_of(people, crew)
    writer.reply = {"headline": "Paddles up at Elm Street!", "lines": ["Sam and Jo rallied."]}
    inside = people.client.get(f"/v1/groups/{crew['group_id']}/recaps/{key}", headers=crew["jo"])
    assert inside.json()["written_by"] == "ai"
    body = card(people, share(people, crew, key).json()["token"])
    assert body["written_by"] == "popshot"
    assert "Elm" not in repr(body)


def test_each_person_has_a_limit_on_live_links(people: People, crew: dict[str, Any]) -> None:
    day_of(people, crew, ["Casey"], ["Gary"], (11, 3))
    key = key_of(people, crew)
    for _ in range(MAX_LIVE_SHARES):
        assert share(people, crew, key).status_code == 201
    assert share(people, crew, key).status_code == 429
    assert share(people, crew, key, "jo").status_code == 201
    turn_off(people, crew, key, "sam")
    assert share(people, crew, key).status_code == 201


def test_with_no_user_the_tables_stay_closed(
    people: People, crew: dict[str, Any], app_engine: Engine
) -> None:
    day_of(people, crew, ["Casey"], ["Gary"], (11, 3))
    share(people, crew, key_of(people, crew))
    with as_user(app_engine, None) as conn:
        for table in ("recap_shares", "matches", "players", "users", "recap_texts"):
            assert conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one() == 0
        # The functions give nothing without a live token.
        for fn in ("app_public_share", "app_public_share_matches", "app_public_share_players"):
            found = conn.execute(
                text(f"SELECT count(*) FROM {fn}(:h)"), {"h": secrets.token_bytes(32)}
            ).scalar_one()
            assert found == 0


def test_the_ai_switch_reaches_shared_links(
    people: People,
    crew: dict[str, Any],
    writer: FakeWriter,
    app_engine: Engine,
    owner_engine: Engine,
) -> None:
    day_of(people, crew, ["Sam"], ["Jo"], (11, 4))
    age(app_engine, people, crew, "2 hours")
    key = key_of(people, crew)
    writer.reply = {"headline": "Paddles up, crew!", "lines": ["Sam and Jo kept rallying."]}
    people.client.get(f"/v1/groups/{crew['group_id']}/recaps/{key}", headers=crew["jo"])
    token = share(people, crew, key).json()["token"]
    assert card(people, token)["written_by"] == "ai"

    def set_rollout(rollout: str) -> None:
        with owner_engine.begin() as conn:
            conn.execute(text("SET LOCAL ROLE popshot_owner"))
            conn.execute(
                text("UPDATE features SET rollout = :r WHERE key = 'recaps.ai'"), {"r": rollout}
            )

    set_rollout("off")
    try:
        assert card(people, token)["written_by"] == "popshot"
    finally:
        set_rollout("everyone")
    assert card(people, token)["written_by"] == "ai"


def test_a_shared_link_follows_the_crews_own_day(
    people: People, crew: dict[str, Any], app_engine: Engine
) -> None:
    # 7pm to 9pm in New York (the crew's zone) runs past midnight UTC: one day, not two.
    ids = [doubles(people, crew, ["Casey"], ["Gary"], (11, 3)) for _ in range(MIN_GAMES)]
    with committed_as(app_engine, people.user_id(crew["casey"])) as conn:
        for hour, match_id in zip((19, 20, 21), ids, strict=True):
            conn.execute(
                text("UPDATE matches SET played_at = :at WHERE id = :id"),
                {"at": f"2026-09-01 {hour}:00-04", "id": match_id},
            )
    token = share(people, crew, key_of(people, crew)).json()["token"]
    assert card(people, token)["games"] == MIN_GAMES
    # The zone is given for a live link only.
    with as_user(app_engine, None) as conn:
        zone = conn.execute(
            text("SELECT app_public_share_zone(:h)"), {"h": secrets.token_bytes(32)}
        ).scalar_one()
    assert zone is None
