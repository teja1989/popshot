# Fixtures shared with other test files are imported, then named as parameters.
# ruff: noqa: F811
"""Find for people with no crew yet (migration 0039, routes/features.py, routes/open_crews.py).

Switches live anywhere show to everyone signed in, by key only. Searching from a typed town
or park goes to Google (FakePlaces here), so it's counted like court search and only works
while Find is live.
"""

from collections.abc import Iterator
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import Engine, text

from popshot_api.places import FakePlaces, PlacesUnavailableError
from tests.db.conftest import People, create
from tests.db.test_events_api import Lists, lists  # noqa: F401  (a fixture)
from tests.db.test_features import Switches, owner, switches  # noqa: F401  (a fixture)
from tests.db.test_places_api import fake, fill, lookups, people  # noqa: F401

pytestmark = pytest.mark.db

Headers = dict[str, str]
FIND = "crew.open"


def live(people: People, who: Headers) -> list[str]:
    response = people.client.get("/v1/me/features", headers=who)
    assert response.status_code == 200, response.text
    found: list[str] = response.json()["live"]
    return found


def test_a_switch_is_live_while_on_for_everyone_or_any_crew(
    people: People, switches: Switches, lists: Lists
) -> None:
    # Someone with no crew at all still sees what's live.
    loner = people.new("Lee")
    key = switches.new(rollout="crews")
    assert key not in live(people, loner)
    lead = people.new("Casey")
    gid = create(people, lead, "Listed Crew")["id"]
    lists.add(key, gid)
    assert key in live(people, loner)
    # The answer is keys only: nothing says which crew.
    assert gid not in people.client.get("/v1/me/features", headers=loner).text
    # A deleted crew doesn't keep it live.
    assert people.client.delete(f"/v1/groups/{gid}", headers=lead).is_success
    assert key not in live(people, loner)
    switches.set(key, rollout="everyone")
    assert key in live(people, loner)
    switches.set(key, rollout="off")
    assert key not in live(people, loner)


@pytest.fixture
def open_crew(people: People, lists: Lists) -> Iterator[dict[str, Any]]:
    """Casey's crew, open and listed at Riverside Park (FakePlaces: 40.80, -73.97)."""
    casey = people.new("Casey")
    gid = create(people, casey, f"Riverside {uuid4().hex[:6]}")["id"]
    lists.add("courts.places", gid)
    lists.add(FIND, gid)
    saved = people.client.post(
        f"/v1/groups/{gid}/courts",
        json={"label": "Riverside courts", "place_id": "fake-riverside-park"},
        headers=casey,
    )
    assert saved.json()["outcome"] == "saved", saved.text
    opened = people.client.put(f"/v1/groups/{gid}/open", json={"open": True}, headers=casey)
    assert opened.status_code == 200, opened.text
    yield {"gid": gid, "casey": casey}
    # Closed again, so other tests' searches near Riverside don't find it.
    people.client.put(f"/v1/groups/{gid}/open", json={"open": False}, headers=casey)


def places_kept(owner_engine: Engine) -> list[tuple[Any, ...]]:
    with owner(owner_engine) as conn:
        return [tuple(r) for r in conn.execute(text("SELECT id, coords_at FROM places")).all()]


def test_someone_with_no_crew_types_a_place_and_finds_crews_near_it(
    people: People, open_crew: dict[str, Any], fake: FakePlaces, owner_engine: Engine
) -> None:
    riley = people.new("Riley")
    me = people.user_id(riley)
    assert FIND in live(people, riley)
    before = lookups(owner_engine, me)
    session = str(uuid4())
    found = people.client.post(
        "/v1/open-crews/places", json={"text": "riverside", "session": session}, headers=riley
    )
    assert found.status_code == 200, found.text
    assert [s["place_id"] for s in found.json()["suggestions"]] == ["fake-riverside-park"]

    kept = places_kept(owner_engine)
    answer = people.client.post(
        "/v1/open-crews/search/place",
        json={"place_id": "fake-riverside-park", "session": session},
        headers=riley,
    )
    assert answer.status_code == 200, answer.text
    assert answer.json()["outcome"] == "found"
    listed = [c for c in answer.json()["crews"] if c["group_id"] == open_crew["gid"]]
    assert [c["court"] for c in listed] == ["Riverside courts"]
    # The pick ends the typed search's Google session; both calls count.
    assert fake.calls[-1] == ("locate", session)
    assert lookups(owner_engine, me) == before + 2
    # The place searched from isn't kept, and its coordinates aren't sent back.
    assert places_kept(owner_engine) == kept
    assert "40.8" not in answer.text


def test_not_found_and_unavailable_are_answers_that_still_count(
    people: People, open_crew: dict[str, Any], fake: FakePlaces, owner_engine: Engine
) -> None:
    riley = people.new("Riley")
    me = people.user_id(riley)
    before = lookups(owner_engine, me)
    nowhere = people.client.post(
        "/v1/open-crews/search/place", json={"place_id": "fake-nowhere"}, headers=riley
    )
    assert nowhere.json() == {"outcome": "not_found", "crews": []}

    def down(*_: Any) -> Any:
        raise PlacesUnavailableError("down")

    fake.suggest = down  # type: ignore[method-assign,assignment]
    fake.locate = down  # type: ignore[method-assign,assignment]
    resting = people.client.post(
        "/v1/open-crews/places", json={"text": "riverside", "session": str(uuid4())}, headers=riley
    )
    assert resting.json() == {"suggestions": [], "unavailable": True}
    gone = people.client.post(
        "/v1/open-crews/search/place", json={"place_id": "fake-riverside-park"}, headers=riley
    )
    assert gone.json() == {"outcome": "unavailable", "crews": []}
    assert lookups(owner_engine, me) == before + 3


def test_typed_searches_need_find_live_and_keep_to_the_limits(
    people: People, open_crew: dict[str, Any], switches: Switches, fill: Any
) -> None:
    riley = people.new("Riley")
    body = {"text": "riverside", "session": str(uuid4())}
    pick = {"place_id": "fake-riverside-park"}
    for bad in ({"place_id": "bad id!"}, {**pick, "radius_km": 0}, {**pick, "extra": 1}):
        assert (
            people.client.post("/v1/open-crews/search/place", json=bad, headers=riley).status_code
            == 422
        )
    # Hourly limits, as for court search.
    me = people.user_id(riley)
    fill("search", 60, me)
    assert people.client.post("/v1/open-crews/places", json=body, headers=riley).status_code == 429
    fill("pick", 20, me)
    assert (
        people.client.post("/v1/open-crews/search/place", json=pick, headers=riley).status_code
        == 429
    )
    # While Find isn't live anywhere, typed searches aren't there: no Google calls.
    switches.set(FIND, rollout="off")
    try:
        other = people.new("Ola")
        assert FIND not in live(people, other)
        assert (
            people.client.post("/v1/open-crews/places", json=body, headers=other).status_code == 404
        )
        assert (
            people.client.post("/v1/open-crews/search/place", json=pick, headers=other).status_code
            == 404
        )
    finally:
        switches.set(FIND, rollout="crews")
