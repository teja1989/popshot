# Fixtures shared with test_places_api.py are imported, then named as parameters.
# ruff: noqa: F811
"""A crew's saved courts (migration 0036, routes/courts.py, ADR 0007).

Google is FakePlaces (test_places_api.py's fixtures). The crew fixture puts its crew on the
courts.places list; typed courts don't need it.
"""

import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError

from popshot_api.places import FakePlaces, PlacesUnavailableError
from tests.db.conftest import People, as_user
from tests.db.test_events_api import Lists, lists  # noqa: F401  (a fixture)
from tests.db.test_features import owner
from tests.db.test_places_api import FEATURE, crew, detail, fake, people  # noqa: F401
from tests.db.test_tick import jobs_engine  # noqa: F401  (a fixture)

pytestmark = pytest.mark.db

Headers = dict[str, str]


def add(people: People, who: Headers, gid: str, label: str, **google: Any) -> Any:
    return people.client.post(
        f"/v1/groups/{gid}/courts", json={"label": label, **google}, headers=who
    )


def courts(people: People, who: Headers, gid: str) -> list[tuple[str, bool]]:
    return [(c["label"], c["is_default"]) for c in detail(people, who, gid)["courts"]]


def test_a_lead_saves_courts_and_the_first_is_the_default(
    people: People, crew: dict[str, Any]
) -> None:
    gid, casey = crew["gid"], crew["casey"]
    first = add(people, casey, gid, "  Riverside courts ")
    assert first.status_code == 200, first.text
    assert first.json()["outcome"] == "saved"
    add(people, casey, gid, "St James indoor")
    assert courts(people, crew["sam"], gid) == [
        ("Riverside courts", True),
        ("St James indoor", False),
    ]


def test_five_at_most_and_names_are_checked(people: People, crew: dict[str, Any]) -> None:
    gid, casey = crew["gid"], crew["casey"]
    for n in range(5):
        assert add(people, casey, gid, f"Court {n}").status_code == 200
    full = add(people, casey, gid, "Court 6")
    assert (full.status_code, full.json()["detail"]) == (409, "A crew can save up to 5 courts.")
    for label in ("", "x" * 81, "See www.example.com"):
        assert add(people, crew["casey"], crew["gid"], label).status_code == 422, label


def test_members_strangers_and_waiting_people_cant(
    people: People, crew: dict[str, Any], app_engine: Engine
) -> None:
    gid = crew["gid"]
    court = add(people, crew["casey"], gid, "Riverside courts").json()["group"]["courts"][0]
    path = f"/v1/groups/{gid}/courts/{court['id']}"
    sam = crew["sam"]
    assert add(people, sam, gid, "Mine").status_code == 403
    assert people.client.patch(path, json={"label": "Mine"}, headers=sam).status_code == 403
    assert people.client.delete(path, headers=sam).status_code == 403
    stranger = people.new("Pat")
    assert add(people, stranger, gid, "Mine").status_code == 404
    assert people.client.delete(path, headers=stranger).status_code == 404
    # Someone waiting to join sees the crew, not its courts.
    waiting = people.new("Wren")
    token = people.client.post(f"/v1/groups/{gid}/invites", json={}, headers=crew["casey"]).json()
    people.client.post("/v1/invites/join", json={"token": token["token"]}, headers=waiting)
    assert detail(people, waiting, gid)["courts"] == []
    with as_user(app_engine, people.user_id(waiting)) as conn:
        assert (
            conn.execute(
                text("SELECT count(*) FROM crew_courts WHERE group_id = :g"), {"g": gid}
            ).scalar_one()
            == 0
        )
    # A member can't write the table directly either.
    with as_user(app_engine, people.user_id(sam)) as conn:
        changed = conn.execute(
            text("UPDATE crew_courts SET label = 'Mine' WHERE group_id = :g"), {"g": gid}
        ).rowcount
    assert changed == 0


def test_one_default_and_removing_it_passes_it_on(people: People, crew: dict[str, Any]) -> None:
    gid, casey = crew["gid"], crew["casey"]
    for label in ("A", "B", "C"):
        add(people, casey, gid, label)
    ids = {c["label"]: c["id"] for c in detail(people, casey, gid)["courts"]}
    made = people.client.patch(
        f"/v1/groups/{gid}/courts/{ids['C']}", json={"is_default": True}, headers=casey
    )
    assert made.status_code == 200, made.text
    assert courts(people, casey, gid) == [("A", False), ("B", False), ("C", True)]
    renamed = people.client.patch(
        f"/v1/groups/{gid}/courts/{ids['C']}", json={"label": "Cee"}, headers=casey
    )
    assert ("Cee", True) in [(c["label"], c["is_default"]) for c in renamed.json()["courts"]]
    gone = people.client.delete(f"/v1/groups/{gid}/courts/{ids['C']}", headers=casey)
    assert gone.status_code == 200
    assert courts(people, casey, gid) == [("A", True), ("B", False)]
    missing = people.client.delete(f"/v1/groups/{gid}/courts/{uuid4()}", headers=casey)
    assert missing.status_code == 404


def test_the_database_keeps_one_default(
    people: People, crew: dict[str, Any], app_engine: Engine
) -> None:
    gid, casey = crew["gid"], crew["casey"]
    add(people, casey, gid, "A")
    add(people, casey, gid, "B")
    with (
        as_user(app_engine, people.user_id(casey)) as conn,
        pytest.raises(DBAPIError, match="crew_courts_one_default"),
    ):
        conn.execute(
            text("UPDATE crew_courts SET is_default = true WHERE group_id = :g"), {"g": gid}
        )


def test_a_google_court_is_counted_and_saved_once(
    people: People, crew: dict[str, Any], fake: FakePlaces, owner_engine: Engine
) -> None:
    gid, casey = crew["gid"], crew["casey"]
    session = str(uuid4())
    saved = add(
        people, casey, gid, "Riverside courts", place_id="fake-riverside-park", session=session
    )
    assert saved.json()["outcome"] == "saved"
    assert fake.calls[-1] == ("locate", session)
    [court] = saved.json()["group"]["courts"]
    assert (court["google_place_id"], court["is_default"]) == ("fake-riverside-park", True)
    calls = len(fake.calls)
    again = add(people, casey, gid, "Again", place_id="fake-riverside-park")
    assert (again.status_code, again.json()["detail"]) == (409, "That court is already saved.")
    # Refused before Google is asked, so nothing went uncounted.
    assert len(fake.calls) == calls
    # Not found and unavailable are answers, and the lookups still count.
    assert add(people, casey, gid, "X", place_id="fake-nowhere").json()["outcome"] == "not_found"
    with owner(owner_engine) as conn:
        picks = conn.execute(
            text("SELECT count(*) FROM place_lookups WHERE user_id = :u AND kind = 'pick'"),
            {"u": people.user_id(casey)},
        ).scalar_one()
    assert picks == 2


def test_google_unavailable_is_an_answer(
    people: People, crew: dict[str, Any], fake: FakePlaces, monkeypatch: pytest.MonkeyPatch
) -> None:
    def down(place_id: str, session: str | None) -> None:
        raise PlacesUnavailableError("down")

    monkeypatch.setattr(fake, "locate", down)
    answer = add(people, crew["casey"], crew["gid"], "X", place_id="fake-riverside-park")
    assert (answer.status_code, answer.json()["outcome"]) == (200, "unavailable")


def test_google_courts_need_the_switch_typed_ones_dont(
    people: People,
    crew: dict[str, Any],
    lists: Lists,
) -> None:
    gid, casey = crew["gid"], crew["casey"]
    lists.remove(FEATURE, gid)
    assert add(people, casey, gid, "R", place_id="fake-riverside-park").status_code == 404
    assert add(people, casey, gid, "Typed").status_code == 200


def test_a_meetup_can_be_at_a_saved_court_and_keeps_its_name(
    people: People, crew: dict[str, Any], app_engine: Engine
) -> None:
    gid, casey = crew["gid"], crew["casey"]
    court = add(people, casey, gid, "Riverside courts", place_id="fake-riverside-park")
    court_id = court.json()["group"]["courts"][0]["id"]
    when = (datetime.now(UTC) + timedelta(days=2)).isoformat()
    body = {"starts_at": when, "venue": "Riverside courts", "court_id": court_id}
    # Any member can plan one there.
    planned = people.client.post(f"/v1/groups/{gid}/nights", json=body, headers=crew["sam"])
    assert planned.status_code == 201, planned.text
    [night] = planned.json() if isinstance(planned.json(), list) else [planned.json()]
    assert (night["court_id"], night["court_google_place_id"]) == (court_id, "fake-riverside-park")
    # Another crew's court, or none at all, is refused.
    other = people.new("Pat")
    other_gid = people.client.post("/v1/groups", json={"name": "Other"}, headers=other).json()["id"]
    theirs = add(people, other, other_gid, "Theirs").json()["group"]["courts"][0]["id"]
    for bad in (theirs, str(uuid4())):
        refused = people.client.post(
            f"/v1/groups/{gid}/nights", json={**body, "court_id": bad}, headers=casey
        )
        assert refused.status_code == 422, bad
    # Removing the court keeps the meetup's venue.
    people.client.delete(f"/v1/groups/{gid}/courts/{court_id}", headers=casey)
    nights = people.client.get(f"/v1/groups/{gid}/nights", headers=casey).json()
    [kept] = [n for n in nights if n["id"] == night["id"]]
    assert (kept["venue"], kept["court_id"]) == ("Riverside courts", None)


def test_the_old_ways_to_set_courts_are_gone(people: People, crew: dict[str, Any]) -> None:
    """Crew courts replaced the home courts and the court on the map (migration 0037)."""
    gid, casey = crew["gid"], crew["casey"]
    profile = {"home_courts": ["Riverside courts"]}
    assert (
        people.client.put(f"/v1/groups/{gid}/profile", json=profile, headers=casey).status_code
        == 422
    )
    body = {"place_id": "fake-sunset-park", "session": str(uuid4()), "label": "Sunset"}
    assert (
        people.client.put(f"/v1/groups/{gid}/home-place", json=body, headers=casey).status_code
        == 404
    )
    assert people.client.delete(f"/v1/groups/{gid}/home-place", headers=casey).status_code == 404
    shown = detail(people, casey, gid)
    assert not {"home_courts", "home_place", "home_place_google_id"} & set(shown)
    assert courts(people, casey, gid) == []


def _migration(name: str) -> Any:
    path = Path(__file__).parents[2] / "migrations" / "versions" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"migration_{name}", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_going_back_and_forth_keeps_the_courts(
    people: People, crew: dict[str, Any], owner_engine: Engine
) -> None:
    """0037's downgrade fills the old columns from crew courts, and 0036's copy brings them
    back. Run as the owner in a transaction that's rolled back, so nothing else sees it."""
    gid, casey = crew["gid"], crew["casey"]
    add(people, casey, gid, "On the map", place_id="fake-riverside-park")
    for label in ("Riverside", "St James", "Hall", "Fourth"):
        add(people, casey, gid, label)
    before = courts(people, casey, gid)
    with owner_engine.connect() as conn:
        transaction = conn.begin()
        try:
            conn.execute(text("SET LOCAL ROLE popshot_owner"))
            conn.execute(text(_migration("0037_drop_old_home_courts").DOWNGRADE))
            old = conn.execute(
                text("SELECT home_courts, home_place_label FROM groups WHERE id = :g"), {"g": gid}
            ).one()
            # The screens before crew courts kept three typed courts at most.
            assert tuple(old) == (["Riverside", "St James", "Hall"], "On the map")
            conn.execute(text("DELETE FROM crew_courts WHERE group_id = :g"), {"g": gid})
            backfill = _migration("0036_crew_courts").BACKFILL
            conn.execute(text(backfill))
            # Running it again adds nothing.
            conn.execute(text(backfill))
            copied = conn.execute(
                text(
                    "SELECT label, is_default FROM crew_courts WHERE group_id = :g "
                    "ORDER BY position, created_at, id"
                ),
                {"g": gid},
            ).all()
            assert [tuple(c) for c in copied] == before[:4]
        finally:
            transaction.rollback()
    assert courts(people, casey, gid) == before


def test_the_job_keeps_and_refreshes_places_saved_courts_use(
    people: People,
    crew: dict[str, Any],
    owner_engine: Engine,
    jobs_engine: Engine,
) -> None:
    gid, casey = crew["gid"], crew["casey"]
    add(people, casey, gid, "R", place_id="fake-riverside-park")
    with owner(owner_engine) as conn:
        conn.execute(
            text(
                "UPDATE places SET coords_at = now() - interval '26 days', "
                "created_at = now() - interval '2 days' "
                "WHERE google_place_id = 'fake-riverside-park'"
            )
        )
    with jobs_engine.begin() as conn:
        due = (
            conn.execute(text("SELECT google_place_id FROM app_jobs_places_to_refresh(500)"))
            .scalars()
            .all()
        )
        assert "fake-riverside-park" in due
        conn.execute(text("SELECT app_jobs_tidy_places()"))
    with owner(owner_engine) as conn:
        kept = conn.execute(
            text("SELECT count(*) FROM places WHERE google_place_id = 'fake-riverside-park'")
        ).scalar_one()
    assert kept == 1
