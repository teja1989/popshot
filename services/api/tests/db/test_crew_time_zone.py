"""A crew's time zone (migration 0040): who sets it, and that only real zones are kept."""

from typing import Any

import pytest
from sqlalchemy import Engine, text

from popshot_api.routes.groups import RENAMED_ZONES
from tests.db.conftest import People, as_user, create
from tests.db.test_crew_profile import detail
from tests.db.test_games_api import join_and_approve

pytestmark = pytest.mark.db

Headers = dict[str, str]


@pytest.fixture
def crew(people: People) -> dict[str, Any]:
    """Casey leads Dawn Dinkers, made in New York, with Sam."""
    casey = people.new("Casey")
    made = people.client.post(
        "/v1/groups",
        json={"name": "Dawn Dinkers", "time_zone": "America/New_York"},
        headers=casey,
    )
    assert made.status_code == 201, made.text
    gid = made.json()["id"]
    sam = join_and_approve(people, casey, gid, "Sam")
    return {"group_id": gid, "casey": casey, "sam": sam, "created": made.json()}


def patch(people: People, who: Headers, gid: str, body: dict[str, Any]) -> Any:
    return people.client.patch(f"/v1/groups/{gid}", json=body, headers=who)


def test_the_creators_zone_is_kept_and_members_see_it(people: People, crew: dict[str, Any]) -> None:
    assert crew["created"]["time_zone"] == "America/New_York"
    assert detail(people, crew["sam"], crew["group_id"])["time_zone"] == "America/New_York"


def test_a_crew_made_without_a_zone_has_none(people: People) -> None:
    assert create(people, people.new("Lee"))["time_zone"] is None


def test_a_zone_postgres_doesnt_know_never_stops_a_crew_being_made(people: People) -> None:
    made = people.client.post(
        "/v1/groups",
        json={"name": "Mars Dinkers", "time_zone": "Mars/Olympus_Mons"},
        headers=people.new("Ari"),
    )
    assert made.status_code == 201, made.text
    assert made.json()["time_zone"] is None


@pytest.mark.parametrize(
    "zone", ["", "../etc/passwd", "America/New York", "/UTC", "x" * 65, "Europe/Kyiv;"]
)
def test_malformed_zones_are_refused(people: People, crew: dict[str, Any], zone: str) -> None:
    made = people.client.post(
        "/v1/groups", json={"name": "Odd", "time_zone": zone}, headers=crew["casey"]
    )
    assert made.status_code == 422
    assert patch(people, crew["casey"], crew["group_id"], {"time_zone": zone}).status_code == 422


def test_leads_change_it_and_other_settings_keep_it(people: People, crew: dict[str, Any]) -> None:
    gid = crew["group_id"]
    changed = patch(people, crew["casey"], gid, {"time_zone": "Europe/London"})
    assert changed.status_code == 200, changed.text
    assert changed.json()["time_zone"] == "Europe/London"
    renamed = patch(people, crew["casey"], gid, {"name": "Dusk Dinkers"})
    assert renamed.json()["time_zone"] == "Europe/London"


def test_an_unknown_zone_is_refused_and_nothing_changes(
    people: People, crew: dict[str, Any]
) -> None:
    gid = crew["group_id"]
    refused = patch(people, crew["casey"], gid, {"time_zone": "Mars/Olympus_Mons"})
    assert refused.status_code == 422
    assert refused.json()["detail"] == "We don't know that time zone."
    assert detail(people, crew["casey"], gid)["time_zone"] == "America/New_York"


def test_members_and_outsiders_cant_change_it(people: People, crew: dict[str, Any]) -> None:
    gid = crew["group_id"]
    assert patch(people, crew["sam"], gid, {"time_zone": "Asia/Tokyo"}).status_code == 403
    assert patch(people, people.new("Max"), gid, {"time_zone": "Asia/Tokyo"}).status_code == 404
    assert detail(people, crew["casey"], gid)["time_zone"] == "America/New_York"


def test_the_database_keeps_only_zones_it_knows(
    people: People, crew: dict[str, Any], app_engine: Engine
) -> None:
    gid = crew["group_id"]
    for zone in ["Mars/Olympus_Mons", "../x", "america/new_york"]:
        with (
            as_user(app_engine, people.user_id(crew["casey"])) as conn,
            pytest.raises(Exception, match="unknown time zone"),
        ):
            conn.execute(
                text("UPDATE groups SET time_zone = :zone WHERE id = :g"), {"zone": zone, "g": gid}
            )


def test_the_database_checks_new_crews_too(
    people: People, crew: dict[str, Any], owner_engine: Engine
) -> None:
    with (
        as_user(owner_engine, None) as conn,
        pytest.raises(Exception, match="unknown time zone"),
    ):
        conn.execute(
            text(
                "INSERT INTO groups (name, created_by, time_zone) "
                "VALUES ('Mars Dinkers', :me, 'Mars/Olympus_Mons')"
            ),
            {"me": people.user_id(crew["casey"])},
        )


def test_a_member_cant_change_it_in_the_database(
    people: People, crew: dict[str, Any], app_engine: Engine
) -> None:
    with as_user(app_engine, people.user_id(crew["sam"])) as conn:
        changed = conn.execute(
            text("UPDATE groups SET time_zone = 'Asia/Tokyo' WHERE id = :g"),
            {"g": crew["group_id"]},
        )
        assert changed.rowcount == 0


def test_old_names_browsers_report_are_kept_under_their_new_names(
    people: People, crew: dict[str, Any]
) -> None:
    made = people.client.post(
        "/v1/groups",
        json={"name": "Chai Dinkers", "time_zone": "Asia/Calcutta"},
        headers=crew["casey"],
    )
    assert made.json()["time_zone"] == "Asia/Kolkata"
    changed = patch(people, crew["casey"], crew["group_id"], {"time_zone": "Europe/Kiev"})
    assert changed.status_code == 200, changed.text
    assert changed.json()["time_zone"] == "Europe/Kyiv"


def test_every_new_name_is_one_postgres_knows(owner_engine: Engine) -> None:
    with as_user(owner_engine, None) as conn:
        known = set(conn.execute(text("SELECT name FROM pg_timezone_names")).scalars())
    assert set(RENAMED_ZONES.values()) <= known
