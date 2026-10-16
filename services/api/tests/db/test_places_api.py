"""Crew courts found with Google Places (migrations 0035 and 0036, routes/places.py and
routes/courts.py).

Google is replaced by FakePlaces. Each test puts its own crew on the courts.places list, so no
global switch changes under other tests. The day's limit is shared by everyone, so tests that
fill it remove their own rows afterwards.
"""

from collections.abc import Iterator
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.exc import ProgrammingError

from popshot_api.main import create_app
from popshot_api.ops.tick import refresh_places
from popshot_api.places import FakePlaces, Location, PlacesUnavailableError
from tests.conftest import make_settings
from tests.db.conftest import INSUFFICIENT_PRIVILEGE, People, as_user, create, sqlstate_of
from tests.db.test_events_api import Lists, lists  # noqa: F401  (a fixture)
from tests.db.test_features import owner
from tests.db.test_games_api import join_and_approve
from tests.db.test_tick import jobs_engine  # noqa: F401  (a fixture)
from tests.fakes import FakeTokenVerifier

pytestmark = pytest.mark.db

Headers = dict[str, str]
FEATURE = "courts.places"


@pytest.fixture
def fake() -> FakePlaces:
    return FakePlaces()


@pytest.fixture
def people(app_engine: Engine, fake: FakePlaces) -> Iterator[People]:
    """The API with FakePlaces in place of Google."""
    verifier = FakeTokenVerifier()
    app = create_app(make_settings(places="fake"), verifier, app_engine, places=fake)
    with TestClient(app) as client:
        yield People(client, verifier)


@pytest.fixture
def crew(people: People, lists: Lists) -> dict[str, Any]:  # noqa: F811
    """Casey leads Court Crew with Sam; the switch is on for it."""
    casey = people.new("Casey")
    gid = create(people, casey, "Court Crew")["id"]
    sam = join_and_approve(people, casey, gid, "Sam")
    lists.add(FEATURE, gid)
    return {"gid": gid, "casey": casey, "sam": sam}


def search(people: People, who: Headers, gid: str, words: str = "riverside") -> Any:
    return people.client.post(
        f"/v1/groups/{gid}/places/search",
        json={"text": words, "session": str(uuid4())},
        headers=who,
    )


def pick(
    people: People, who: Headers, gid: str, place_id: str = "fake-riverside-park", **over: Any
) -> Any:
    body = {"place_id": place_id, "session": str(uuid4()), "label": "Riverside courts", **over}
    return people.client.post(f"/v1/groups/{gid}/courts", json=body, headers=who)


def detail(people: People, who: Headers, gid: str) -> dict[str, Any]:
    response = people.client.get(f"/v1/groups/{gid}", headers=who)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def on_map(group: dict[str, Any]) -> tuple[str, str] | None:
    """The crew's saved court from Google, by its name and Google's ID."""
    found = [(c["label"], c["google_place_id"]) for c in group["courts"] if c["google_place_id"]]
    return found[0] if found else None


def lookups(owner_engine: Engine, user_id: UUID | None = None) -> int:
    with owner(owner_engine) as conn:
        count: int = conn.execute(
            text(
                "SELECT count(*) FROM place_lookups "
                "WHERE user_id IS NOT DISTINCT FROM :u AND at >= date_trunc('day', now())"
            ),
            {"u": user_id},
        ).scalar_one()
    return count


@pytest.fixture
def fill(owner_engine: Engine) -> Iterator[Any]:
    """Add lookup rows as if made earlier; removes them after the test."""
    added: list[int] = []

    def add(kind: str, count: int, user_id: UUID | None = None) -> None:
        with owner(owner_engine) as conn:
            ids = conn.execute(
                text(
                    "INSERT INTO place_lookups (user_id, kind) "
                    "SELECT :u, :k FROM generate_series(1, :n) RETURNING id"
                ),
                {"u": user_id, "k": kind, "n": count},
            ).scalars()
            added.extend(ids)

    yield add
    with owner(owner_engine) as conn:
        conn.execute(text("DELETE FROM place_lookups WHERE id = ANY(:ids)"), {"ids": added})


def test_a_lead_searches_picks_and_names_a_court(
    people: People, crew: dict[str, Any], fake: FakePlaces
) -> None:
    gid = crew["gid"]
    found = search(people, crew["casey"], gid, "riverside")
    assert found.status_code == 200, found.text
    assert found.json() == {
        "suggestions": [
            {
                "place_id": "fake-riverside-park",
                "main": "Riverside Park Pickleball Courts",
                "secondary": "Riverside Dr, Springfield",
            }
        ],
        "unavailable": False,
    }

    session = str(uuid4())
    saved = pick(people, crew["casey"], gid, session=session, label="  Riverside courts ")
    assert saved.status_code == 200, saved.text
    assert saved.json()["outcome"] == "saved"
    assert on_map(saved.json()["group"]) == ("Riverside courts", "fake-riverside-park")
    # The pick ends the search's Google session.
    assert fake.calls[-1] == ("locate", session)
    # Members see it by the crew's own name, with Google's ID for an "Open in Maps" link.
    assert on_map(detail(people, crew["sam"], gid)) == ("Riverside courts", "fake-riverside-park")


def test_only_ids_and_fresh_coordinates_are_kept(
    people: People, crew: dict[str, Any], owner_engine: Engine
) -> None:
    assert pick(people, crew["casey"], crew["gid"]).json()["outcome"] == "saved"
    with owner(owner_engine) as conn:
        place = (
            conn.execute(
                text(
                    "SELECT p.*, now() - p.coords_at < interval '1 minute' AS fresh FROM places p "
                    "WHERE google_place_id = 'fake-riverside-park'"
                )
            )
            .mappings()
            .one()
        )
    assert (place["lat"], place["lng"], place["fresh"]) == (40.80, -73.97, True)
    # Nothing of Google's name or address: the table has no column for it.
    assert set(place) == {"id", "google_place_id", "lat", "lng", "coords_at", "created_at", "fresh"}


def test_members_strangers_and_waiting_people_cant(people: People, crew: dict[str, Any]) -> None:
    gid = crew["gid"]
    assert search(people, crew["sam"], gid).status_code == 403
    assert pick(people, crew["sam"], gid).status_code == 403
    stranger = people.new("Stranger")
    assert search(people, stranger, gid).status_code == 404
    assert pick(people, stranger, gid).status_code == 404
    assert pick(people, crew["casey"], gid).json()["outcome"] == "saved"
    # Someone waiting to join sees the crew, but not its courts.
    waiting = people.new("Wren")
    token = people.client.post(f"/v1/groups/{gid}/invites", json={}, headers=crew["casey"]).json()
    people.client.post("/v1/invites/join", json={"token": token["token"]}, headers=waiting)
    hidden = detail(people, waiting, gid)
    assert hidden["courts"] == []


def test_hidden_while_the_switch_is_off_or_places_are_off(
    people: People,
    crew: dict[str, Any],
    lists: Lists,  # noqa: F811
    app_engine: Engine,
) -> None:
    lists.remove(FEATURE, crew["gid"])
    assert search(people, crew["casey"], crew["gid"]).status_code == 404
    assert pick(people, crew["casey"], crew["gid"]).status_code == 404
    lists.add(FEATURE, crew["gid"])
    # An API with places off (the default) has no such routes.
    with TestClient(create_app(make_settings(), people.verifier, app_engine)) as client:
        answer = client.post(
            f"/v1/groups/{crew['gid']}/places/search",
            json={"text": "riverside", "session": str(uuid4())},
            headers=crew["casey"],
        )
    assert answer.status_code == 404


def test_names_are_checked(people: People, crew: dict[str, Any]) -> None:
    for label in ("", "x" * 81, "see www.example.com", "courts\u0000"):
        assert pick(people, crew["casey"], crew["gid"], label=label).status_code == 422
    assert pick(people, crew["casey"], crew["gid"], place_id="bad id!").status_code == 422


def test_an_unknown_place_is_an_answer_and_still_counts(
    people: People, crew: dict[str, Any], owner_engine: Engine
) -> None:
    casey = people.user_id(crew["casey"])
    before = lookups(owner_engine, casey)
    answer = pick(people, crew["casey"], crew["gid"], place_id="fake-nowhere")
    assert answer.status_code == 200
    assert answer.json()["outcome"] == "not_found"
    assert answer.json()["group"]["courts"] == []
    # Not rolled back with an error: the lookup Google answered is counted.
    assert lookups(owner_engine, casey) == before + 1


def test_google_being_unreachable_is_an_answer_and_still_counts(
    people: People, crew: dict[str, Any], fake: FakePlaces, owner_engine: Engine
) -> None:
    def down(*_: Any) -> Any:
        raise PlacesUnavailableError("down")

    fake.suggest = down  # type: ignore[method-assign,assignment]
    fake.locate = down  # type: ignore[method-assign,assignment]
    casey = people.user_id(crew["casey"])
    before = lookups(owner_engine, casey)
    assert search(people, crew["casey"], crew["gid"]).json() == {
        "suggestions": [],
        "unavailable": True,
    }
    assert pick(people, crew["casey"], crew["gid"]).json()["outcome"] == "unavailable"
    assert lookups(owner_engine, casey) == before + 2


def test_each_person_has_an_hourly_limit(people: People, crew: dict[str, Any], fill: Any) -> None:
    casey = people.user_id(crew["casey"])
    fill("search", 60, casey)
    limited = search(people, crew["casey"], crew["gid"])
    assert limited.status_code == 429
    assert "a lot of searching" in limited.json()["detail"]
    fill("pick", 20, casey)
    assert pick(people, crew["casey"], crew["gid"]).status_code == 429
    # Someone else isn't held back by Casey's searching.
    other = people.new("Ola")
    gid = create(people, other, "Other Crew")["id"]
    assert search(people, other, gid).status_code == 404  # (their crew isn't on the list)


def test_everyone_together_has_a_daily_limit(
    people: People, crew: dict[str, Any], fill: Any, owner_engine: Engine
) -> None:
    used = 330 - lookups_today(owner_engine, "search")
    fill("search", used)
    resting = search(people, crew["casey"], crew["gid"])
    assert resting.status_code == 503
    assert "resting until tomorrow" in resting.json()["detail"]
    # Picks and the job's refreshes share the other day's limit.
    fill(
        "refresh",
        330 - lookups_today(owner_engine, "pick") - lookups_today(owner_engine, "refresh"),
    )
    assert pick(people, crew["casey"], crew["gid"]).status_code == 503


def lookups_today(owner_engine: Engine, kind: str) -> int:
    with owner(owner_engine) as conn:
        count: int = conn.execute(
            text(
                "SELECT count(*) FROM place_lookups "
                "WHERE kind = :k AND at >= date_trunc('day', now())"
            ),
            {"k": kind},
        ).scalar_one()
    return count


def test_the_app_reads_places_only_through_crews_and_never_writes_them(
    people: People, crew: dict[str, Any], app_engine: Engine
) -> None:
    assert pick(people, crew["casey"], crew["gid"]).json()["outcome"] == "saved"
    sam = people.user_id(crew["sam"])
    outsider = people.user_id(people.new("Out"))
    with as_user(app_engine, sam) as conn:
        assert conn.execute(text("SELECT count(*) FROM places")).scalar_one() >= 1
    with as_user(app_engine, outsider) as conn:
        seen = conn.execute(
            text("SELECT count(*) FROM places WHERE google_place_id = 'fake-riverside-park'")
        ).scalar_one()
        assert seen == 0
    for sql in (
        "INSERT INTO places (google_place_id) VALUES ('sneaky')",
        "UPDATE places SET lat = 0, lng = 0, coords_at = now()",
        "INSERT INTO place_lookups (user_id, kind) VALUES (:me, 'search')",
        "DELETE FROM place_lookups",
    ):
        with as_user(app_engine, sam) as conn, pytest.raises(ProgrammingError, match="denied"):
            conn.execute(text(sql), {"me": sam})
    # Upserting needs someone signed in.
    with as_user(app_engine, None) as conn:
        assert sqlstate_of(conn, "SELECT app_upsert_place('x', 1, 1)") == INSUFFICIENT_PRIVILEGE


def test_you_see_only_your_own_lookups(
    people: People, crew: dict[str, Any], app_engine: Engine
) -> None:
    search(people, crew["casey"], crew["gid"])
    with as_user(app_engine, people.user_id(crew["sam"])) as conn:
        mine = conn.execute(text("SELECT count(*) FROM place_lookups")).scalar_one()
    assert mine == 0


def test_the_job_refreshes_coordinates_and_tidies_up(
    people: People,
    crew: dict[str, Any],
    owner_engine: Engine,
    jobs_engine: Engine,  # noqa: F811
) -> None:
    assert pick(people, crew["casey"], crew["gid"]).json()["outcome"] == "saved"
    with owner(owner_engine) as conn:
        # 26 days old: due for a refresh. And an unused place, two days old: to be dropped.
        conn.execute(
            text(
                "UPDATE places SET coords_at = now() - interval '26 days', lat = 1, lng = 1 "
                "WHERE google_place_id = 'fake-riverside-park'"
            )
        )
        conn.execute(
            text(
                "INSERT INTO places (google_place_id, created_at) "
                "VALUES ('fake-unused', now() - interval '2 days')"
            )
        )

    class Moved(FakePlaces):
        def locate(self, place_id: str, session: str | None) -> Location | None:
            return Location(place_id=place_id, lat=40.81, lng=-73.96)

    assert refresh_places(jobs_engine, Moved()) >= 1
    with owner(owner_engine) as conn:
        place = (
            conn.execute(
                text(
                    "SELECT lat, lng, now() - coords_at < interval '1 minute' AS fresh FROM places "
                    "WHERE google_place_id = 'fake-riverside-park'"
                )
            )
            .mappings()
            .one()
        )
        unused = conn.execute(
            text("SELECT count(*) FROM places WHERE google_place_id = 'fake-unused'")
        ).scalar_one()
    assert dict(place) == {"lat": 40.81, "lng": -73.96, "fresh": True}
    assert unused == 0


def test_coordinates_older_than_thirty_days_are_cleared(
    people: People,
    crew: dict[str, Any],
    owner_engine: Engine,
    jobs_engine: Engine,  # noqa: F811
) -> None:
    assert pick(people, crew["casey"], crew["gid"]).json()["outcome"] == "saved"
    with owner(owner_engine) as conn:
        conn.execute(
            text(
                "UPDATE places SET coords_at = now() - interval '31 days' "
                "WHERE google_place_id = 'fake-riverside-park'"
            )
        )
    # Google can't be reached: no refresh, so Google's 30 days end with the tidy-up.
    refresh_places(jobs_engine, None)
    with owner(owner_engine) as conn:
        row = conn.execute(
            text("SELECT lat, coords_at FROM places WHERE google_place_id = 'fake-riverside-park'")
        ).one()
    assert tuple(row) == (None, None)
    # The crew keeps its court and its name for it.
    assert on_map(detail(people, crew["sam"], crew["gid"])) == (
        "Riverside courts",
        "fake-riverside-park",
    )


def test_the_tidy_up_drops_lookup_counts_after_two_days(
    people: People,
    crew: dict[str, Any],
    owner_engine: Engine,
    jobs_engine: Engine,  # noqa: F811
) -> None:
    # Even on a day nobody searches, the counts go after 2 days, as the privacy page says.
    search(people, crew["casey"], crew["gid"])
    casey = people.user_id(crew["casey"])
    with owner(owner_engine) as conn:
        conn.execute(
            text("UPDATE place_lookups SET at = now() - interval '3 days' WHERE user_id = :u"),
            {"u": casey},
        )
        conn.execute(
            text("INSERT INTO place_lookups (user_id, kind) VALUES (:u, 'search')"), {"u": casey}
        )
    refresh_places(jobs_engine, None)
    with owner(owner_engine) as conn:
        ages = (
            conn.execute(
                text("SELECT at > now() - interval '1 hour' FROM place_lookups WHERE user_id = :u"),
                {"u": casey},
            )
            .scalars()
            .all()
        )
    assert ages == [True]


def test_only_the_job_runs_the_job_functions(people: People, app_engine: Engine) -> None:
    riley = people.user_id(people.new("Riley"))
    for call in (
        "SELECT app_jobs_place_lookup()",
        "SELECT * FROM app_jobs_places_to_refresh(1)",
        "SELECT app_jobs_place_coords(gen_random_uuid(), 1, 1)",
        "SELECT app_jobs_tidy_places()",
    ):
        with as_user(app_engine, riley) as conn, pytest.raises(ProgrammingError, match="denied"):
            conn.execute(text(call))


def test_your_lookups_are_in_your_download_and_go_with_your_account(
    people: People, crew: dict[str, Any], owner_engine: Engine
) -> None:
    search(people, crew["casey"], crew["gid"])
    data = people.client.get("/v1/me/export", headers=crew["casey"]).json()
    assert [row["kind"] for row in data["court_searches"]][-1] == "search"
    casey = people.user_id(crew["casey"])
    with owner(owner_engine) as conn:
        conn.execute(text("UPDATE users SET deleted_at = now() WHERE id = :u"), {"u": casey})
        left = conn.execute(
            text("SELECT count(*) FROM place_lookups WHERE user_id = :u"), {"u": casey}
        ).scalar_one()
    assert left == 0
