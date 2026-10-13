"""The crew profile (migration 0022): about, usual times, home courts, and who sees what."""

import secrets
from typing import Any

import pytest
from sqlalchemy import Engine, text

from tests.db.conftest import People, as_user, create
from tests.db.test_direct_invites_api import code_of, inbox, invite, person
from tests.db.test_games_api import join_and_approve

pytestmark = pytest.mark.db

Headers = dict[str, str]

PROFILE = {
    "about": "Friendly games, all levels. We rotate partners.",
    "usual_days": ["thu", "tue", "sat"],
    "usual_times": ["evening", "morning"],
    "home_courts": ["Riverside Park courts", "St. James Rec"],
}


@pytest.fixture
def crew(people: People) -> dict[str, Any]:
    """Casey leads Dawn Dinkers with Sam."""
    casey = people.new("Casey")
    gid = create(people, casey, name="Dawn Dinkers")["id"]
    sam = join_and_approve(people, casey, gid, "Sam")
    return {"group_id": gid, "casey": casey, "sam": sam}


def set_profile(people: People, who: Headers, gid: str, profile: dict[str, Any]) -> Any:
    return people.client.put(f"/v1/groups/{gid}/profile", json=profile, headers=who)


def detail(people: People, who: Headers, gid: str) -> dict[str, Any]:
    response = people.client.get(f"/v1/groups/{gid}", headers=who)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def test_leads_set_the_profile_and_members_see_it(people: People, crew: dict[str, Any]) -> None:
    gid = crew["group_id"]
    saved = set_profile(people, crew["casey"], gid, PROFILE)
    assert saved.status_code == 200, saved.text
    seen = detail(people, crew["sam"], gid)
    assert seen["about"] == PROFILE["about"]
    # Days and times come back in week and day order.
    assert seen["usual_days"] == ["tue", "thu", "sat"]
    assert seen["usual_times"] == ["morning", "evening"]
    assert seen["home_courts"] == PROFILE["home_courts"]
    # Members can't change it.
    assert set_profile(people, crew["sam"], gid, PROFILE).status_code == 403
    # Clearing it.
    cleared = set_profile(people, crew["casey"], gid, {"about": "  "})
    assert cleared.status_code == 200
    assert cleared.json()["about"] is None
    assert cleared.json()["home_courts"] == []


@pytest.mark.parametrize(
    "profile",
    [
        {"about": "Join us at https://example.com"},
        {"about": "See www.dawndinkers.org"},
        {"about": "Email casey@example.com to join"},
        {"about": "Find us on dinkers.app"},
        {"about": "x" * 201},
        {"home_courts": ["Visit courts.com"]},
        {"home_courts": ["A", "B", "C", "D"]},
        {"home_courts": ["x" * 81]},
        {"usual_days": ["monday"]},
        {"usual_times": ["night"]},
        {"about": "Tab\u0000here"},
    ],
)
def test_the_profile_refuses_links_and_oversize_values(
    people: People, crew: dict[str, Any], profile: dict[str, Any]
) -> None:
    assert set_profile(people, crew["casey"], crew["group_id"], profile).status_code == 422


def test_normal_text_with_dots_is_fine(people: People, crew: dict[str, Any]) -> None:
    profile = {"about": "Dr. Lee's group, e.g. drills first.", "home_courts": ["St. James Rec"]}
    assert set_profile(people, crew["casey"], crew["group_id"], profile).status_code == 200


def test_the_database_refuses_links_too(
    people: People, crew: dict[str, Any], app_engine: Engine
) -> None:
    with (
        as_user(app_engine, people.user_id(crew["casey"])) as conn,
        pytest.raises(Exception, match="check"),
    ):
        conn.execute(
            text("UPDATE groups SET about = 'go to https://x.example' WHERE id = :g"),
            {"g": crew["group_id"]},
        )


def test_people_not_in_the_crew_see_about_and_times_but_never_courts(
    people: People, crew: dict[str, Any]
) -> None:
    gid = crew["group_id"]
    set_profile(people, crew["casey"], gid, PROFILE)

    # Through an invite link's preview.
    link = people.client.post(
        f"/v1/groups/{gid}/invites", json={"max_uses": 3}, headers=crew["casey"]
    ).json()["token"]
    riley = people.new("Riley")
    preview = people.client.post("/v1/invites/preview", json={"token": link}, headers=riley)
    assert preview.status_code == 200, preview.text
    shown = preview.json()
    assert shown["about"] == PROFILE["about"]
    assert shown["usual_days"] == ["tue", "thu", "sat"]
    assert "home_courts" not in shown
    assert "Riverside" not in preview.text

    # While waiting to be let in: still no courts.
    people.client.post("/v1/invites/join", json={"token": link}, headers=riley)
    waiting = detail(people, riley, gid)
    assert waiting["my_status"] == "pending"
    assert waiting["home_courts"] == []
    assert waiting["about"] == PROFILE["about"]

    # In the invites inbox.
    robin = people.new("Robin")
    found = person(people, crew["casey"], gid, code_of(people, robin))
    assert found is not None
    invite(people, crew["casey"], gid, found["user_id"])
    response = people.client.get("/v1/me/invites", headers=robin)
    [mine] = inbox(people, robin)
    assert mine["about"] == PROFILE["about"]
    assert mine["usual_times"] == ["morning", "evening"]
    assert "Riverside" not in response.text


def test_the_preview_functions_never_return_courts(
    people: People, crew: dict[str, Any], app_engine: Engine
) -> None:
    """Even called straight in the database, by someone outside the crew."""
    set_profile(people, crew["casey"], crew["group_id"], PROFILE)
    outsider = people.user_id(people.new("Pat"))
    with as_user(app_engine, outsider) as conn:
        for fn in ("app_preview_invite(:h)", "app_my_direct_invites()"):
            columns = conn.execute(
                text(f"SELECT * FROM {fn} LIMIT 0"), {"h": secrets.token_bytes(32)}
            ).keys()
            assert "home_courts" not in columns
