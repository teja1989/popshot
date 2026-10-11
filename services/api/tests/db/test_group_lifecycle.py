"""Group settings, leaving, handing over the lead, restoring people, deleting and restoring
a group, against the real database."""

from typing import Any

import pytest
from sqlalchemy import Engine, text

from tests.db.conftest import People, as_user, create
from tests.db.test_games_api import join_and_approve, log, players

pytestmark = pytest.mark.db

Headers = dict[str, str]


@pytest.fixture
def crew(people: People) -> dict[str, Any]:
    """Casey (lead), Sam (co-lead) and Jo (member), with one game between Casey and Jo."""
    casey = people.new("Casey")
    group_id = create(people, casey)["id"]
    sam = join_and_approve(people, casey, group_id, "Sam")
    jo = join_and_approve(people, casey, group_id, "Jo")
    assert change(people, casey, group_id, people.user_id(sam), "make_co_lead").status_code == 200
    ids = {name: p["id"] for name, p in players(people, casey, group_id).items()}
    game = log(
        people,
        casey,
        group_id,
        format="singles",
        team_a=[ids["Casey"]],
        team_b=[ids["Jo"]],
        games=[{"team_a": 11, "team_b": 6}],
    )
    assert game.status_code == 201, game.text
    return {
        "group_id": group_id,
        "casey": casey,
        "sam": sam,
        "jo": jo,
        "match_id": game.json()["id"],
    }


def change(people: People, headers: Headers, group_id: str, user_id: Any, action: str) -> Any:
    return people.client.patch(
        f"/v1/groups/{group_id}/members/{user_id}", json={"action": action}, headers=headers
    )


def group(people: People, headers: Headers, group_id: str) -> Any:
    return people.client.get(f"/v1/groups/{group_id}", headers=headers)


def my_groups(people: People, headers: Headers) -> list[str]:
    return [g["id"] for g in people.client.get("/v1/groups", headers=headers).json()]


def invite_token(people: People, headers: Headers, group_id: str) -> str:
    response = people.client.post(f"/v1/groups/{group_id}/invites", json={}, headers=headers)
    assert response.status_code == 201, response.text
    token: str = response.json()["token"]
    return token


def join(people: People, headers: Headers, token: str) -> Any:
    return people.client.post("/v1/invites/join", json={"token": token}, headers=headers)


# Settings


def test_admins_rename_and_change_rules(people: People, crew: dict[str, Any]) -> None:
    gid = crew["group_id"]
    renamed = people.client.patch(
        f"/v1/groups/{gid}", json={"name": "  Night Owls "}, headers=crew["casey"]
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["name"] == "Night Owls"
    rules = people.client.patch(
        f"/v1/groups/{gid}",
        json={"default_format": "singles", "default_points_to": 15, "default_win_by_two": False},
        headers=crew["sam"],
    ).json()
    assert (rules["name"], rules["default_format"], rules["default_points_to"]) == (
        "Night Owls",
        "singles",
        15,
    )
    assert rules["default_win_by_two"] is False
    # Nothing given: nothing changes.
    assert (
        people.client.patch(f"/v1/groups/{gid}", json={}, headers=crew["casey"]).json()["name"]
        == "Night Owls"
    )


@pytest.mark.parametrize(
    "body",
    [
        {"name": ""},
        {"name": "x" * 61},
        {"name": "a\u0000b"},
        {"default_points_to": 12},
        {"owner": "me"},
    ],
)
def test_settings_are_validated(people: People, crew: dict[str, Any], body: dict[str, Any]) -> None:
    response = people.client.patch(
        f"/v1/groups/{crew['group_id']}", json=body, headers=crew["casey"]
    )
    assert response.status_code == 422


def test_members_and_outsiders_cant_change_settings(people: People, crew: dict[str, Any]) -> None:
    gid = crew["group_id"]
    assert (
        people.client.patch(
            f"/v1/groups/{gid}", json={"name": "Mine"}, headers=crew["jo"]
        ).status_code
        == 403
    )
    outsider = people.new("Riley")
    assert (
        people.client.patch(
            f"/v1/groups/{gid}", json={"name": "Mine"}, headers=outsider
        ).status_code
        == 404
    )


# Leaving and coming back


def test_a_member_leaves_and_their_games_stay(people: People, crew: dict[str, Any]) -> None:
    gid = crew["group_id"]
    left = people.client.post(f"/v1/groups/{gid}/leave", headers=crew["jo"])
    assert left.status_code == 204
    assert gid not in my_groups(people, crew["jo"])
    assert group(people, crew["jo"], gid).status_code == 404
    names = [m["display_name"] for m in group(people, crew["casey"], gid).json()["members"]]
    assert "Jo" not in names
    # The game is still there for everyone else.
    games = people.client.get(f"/v1/groups/{gid}/matches", headers=crew["casey"]).json()
    assert [g["id"] for g in games] == [crew["match_id"]]
    # Someone who left isn't offered to admins for restoring.
    assert group(people, crew["casey"], gid).json()["former_members"] == []
    assert (
        change(people, crew["casey"], gid, people.user_id(crew["jo"]), "restore").status_code == 404
    )


def test_someone_who_left_can_ask_to_join_again(people: People, crew: dict[str, Any]) -> None:
    gid = crew["group_id"]
    people.client.post(f"/v1/groups/{gid}/leave", headers=crew["jo"])
    token = invite_token(people, crew["casey"], gid)
    # The preview treats them as new, so they're offered to ask.
    preview = people.client.post("/v1/invites/preview", json={"token": token}, headers=crew["jo"])
    assert (preview.json()["my_status"], preview.json()["group_id"]) == (None, None)
    joined = join(people, crew["jo"], token)
    assert joined.json() == {"group_id": gid, "status": "pending"}
    jo_id = people.user_id(crew["jo"])
    assert change(people, crew["casey"], gid, jo_id, "approve").status_code == 200
    back = {m["display_name"]: m for m in group(people, crew["jo"], gid).json()["members"]}
    assert back["Jo"]["status"] == "active"
    # Same player as before, so their history carries on.
    assert len([p for p in players(people, crew["casey"], gid) if p == "Jo"]) == 1


def test_the_lead_must_hand_over_before_leaving(people: People, crew: dict[str, Any]) -> None:
    gid = crew["group_id"]
    refused = people.client.post(f"/v1/groups/{gid}/leave", headers=crew["casey"])
    assert refused.status_code == 409
    assert "lead" in refused.json()["detail"]

    sam_id = people.user_id(crew["sam"])
    # Only the lead hands over, and only to someone already in.
    assert (
        change(people, crew["sam"], gid, people.user_id(crew["jo"]), "make_lead").status_code == 403
    )
    handed = change(people, crew["casey"], gid, sam_id, "make_lead")
    assert handed.status_code == 200, handed.text
    roles = {m["display_name"]: m["role"] for m in handed.json()["members"]}
    assert (roles["Sam"], roles["Casey"]) == ("lead", "co_lead")
    assert handed.json()["my_role"] == "co_lead"

    assert people.client.post(f"/v1/groups/{gid}/leave", headers=crew["casey"]).status_code == 204
    assert group(people, crew["sam"], gid).json()["my_role"] == "lead"


def test_cant_hand_over_to_someone_waiting(people: People, crew: dict[str, Any]) -> None:
    gid = crew["group_id"]
    waiting = people.new("Alex")
    join(people, waiting, invite_token(people, crew["casey"], gid))
    response = change(people, crew["casey"], gid, people.user_id(waiting), "make_lead")
    assert response.status_code == 409


def test_cancel_a_join_request(people: People, crew: dict[str, Any]) -> None:
    gid = crew["group_id"]
    waiting = people.new("Alex")
    join(people, waiting, invite_token(people, crew["casey"], gid))
    assert people.client.post(f"/v1/groups/{gid}/leave", headers=waiting).status_code == 204
    statuses = [m["status"] for m in group(people, crew["casey"], gid).json()["members"]]
    assert "pending" not in statuses


# Restoring removed and declined people


def test_admins_restore_removed_and_declined_people(people: People, crew: dict[str, Any]) -> None:
    gid = crew["group_id"]
    jo_id = people.user_id(crew["jo"])
    assert change(people, crew["casey"], gid, jo_id, "remove").status_code == 200
    declined = people.new("Alex")
    join(people, declined, invite_token(people, crew["casey"], gid))
    alex_id = people.user_id(declined)
    assert change(people, crew["sam"], gid, alex_id, "decline").status_code == 200

    former = group(people, crew["sam"], gid).json()["former_members"]
    assert {f["display_name"] for f in former} == {"Jo", "Alex"}
    # Removed and declined people can't get back in with a link.
    assert (
        join(people, declined, invite_token(people, crew["casey"], gid)).json()["status"]
        == "removed"
    )

    restored = change(people, crew["sam"], gid, alex_id, "restore")
    assert restored.status_code == 200, restored.text
    assert {m["display_name"]: m["status"] for m in restored.json()["members"]}["Alex"] == "active"
    assert {f["display_name"] for f in restored.json()["former_members"]} == {"Jo"}
    # A declined person never had a player record; restoring makes one.
    assert "Alex" in players(people, crew["casey"], gid)
    # Restoring someone who's in already is a 404, as is any other action on a removed person.
    assert change(people, crew["sam"], gid, alex_id, "restore").status_code == 404
    assert change(people, crew["casey"], gid, jo_id, "approve").status_code == 404


def test_members_dont_see_former_members(people: People, crew: dict[str, Any]) -> None:
    gid = crew["group_id"]
    change(people, crew["casey"], gid, people.user_id(crew["jo"]), "remove")
    member = join_and_approve(people, crew["casey"], gid, "Alex")
    assert group(people, member, gid).json()["former_members"] == []
    assert change(people, member, gid, people.user_id(crew["jo"]), "restore").status_code == 403


# Deleting and restoring a group


def test_only_the_lead_deletes(people: People, crew: dict[str, Any]) -> None:
    gid = crew["group_id"]
    assert people.client.delete(f"/v1/groups/{gid}", headers=crew["sam"]).status_code == 403
    assert people.client.delete(f"/v1/groups/{gid}", headers=crew["jo"]).status_code == 403
    assert people.client.delete(f"/v1/groups/{gid}", headers=people.new("Riley")).status_code == 404


def test_a_deleted_group_disappears_for_everyone_until_restored(
    people: People, crew: dict[str, Any]
) -> None:
    gid = crew["group_id"]
    token = invite_token(people, crew["casey"], gid)
    assert people.client.delete(f"/v1/groups/{gid}", headers=crew["casey"]).status_code == 204

    for who in ("casey", "sam", "jo"):
        headers = crew[who]
        assert gid not in my_groups(people, headers)
        assert group(people, headers, gid).status_code == 404
        assert people.client.get(f"/v1/groups/{gid}/matches", headers=headers).status_code == 404
        assert people.client.get(f"/v1/groups/{gid}/board", headers=headers).status_code == 404
    # Its invites are dead.
    assert join(people, people.new("Alex"), token).status_code == 404
    assert (
        people.client.post(
            "/v1/invites/preview", json={"token": token}, headers=crew["jo"]
        ).status_code
        == 404
    )

    # Only the lead sees it to restore.
    deleted = people.client.get("/v1/groups/deleted", headers=crew["casey"]).json()
    assert [(d["id"], d["name"]) for d in deleted] == [(gid, "Tuesday Dinkers")]
    assert people.client.get("/v1/groups/deleted", headers=crew["sam"]).json() == []
    assert people.client.post(f"/v1/groups/{gid}/restore", headers=crew["sam"]).status_code == 404

    restored = people.client.post(f"/v1/groups/{gid}/restore", headers=crew["casey"])
    assert restored.status_code == 200, restored.text
    assert gid in my_groups(people, crew["jo"])
    games = people.client.get(f"/v1/groups/{gid}/matches", headers=crew["jo"]).json()
    assert [g["id"] for g in games] == [crew["match_id"]]
    # Invites stay revoked after a restore.
    assert join(people, people.new("Alex"), token).status_code == 404


def test_rows_of_a_deleted_group_are_hidden_at_the_database(
    people: People, crew: dict[str, Any], app_engine: Engine
) -> None:
    gid = crew["group_id"]
    people.client.delete(f"/v1/groups/{gid}", headers=crew["casey"])
    with as_user(app_engine, people.user_id(crew["casey"])) as conn:
        for table in ("groups", "players", "matches", "match_games", "match_players"):
            column = "id" if table == "groups" else "group_id"
            count = conn.execute(
                text(f"SELECT count(*) FROM {table} WHERE {column} = :g"),
                {"g": gid},
            ).scalar_one()
            assert count == 0, table
        # And can't be written to.
        assert (
            conn.execute(text("UPDATE groups SET name = 'x' WHERE id = :g"), {"g": gid}).rowcount
            == 0
        )


def test_restore_window_and_purge(
    people: People, crew: dict[str, Any], owner_engine: Engine
) -> None:
    gid = crew["group_id"]
    people.client.delete(f"/v1/groups/{gid}", headers=crew["casey"])
    other = people.new("Riley")
    kept = create(people, other, "Recently Gone")["id"]
    people.client.delete(f"/v1/groups/{kept}", headers=other)

    with owner_engine.begin() as conn:
        conn.execute(
            text("UPDATE groups SET deleted_at = now() - interval '31 days' WHERE id = :g"),
            {"g": gid},
        )
    # Past the window: not listed, can't be restored.
    assert people.client.get("/v1/groups/deleted", headers=crew["casey"]).json() == []
    assert people.client.post(f"/v1/groups/{gid}/restore", headers=crew["casey"]).status_code == 404

    with owner_engine.begin() as conn:
        purged = conn.execute(text("SELECT app_purge_deleted_groups()")).scalar_one()
        assert purged >= 1
        left = conn.execute(
            text("SELECT id FROM groups WHERE id = ANY(:ids)"), {"ids": [gid, kept]}
        ).scalars()
        assert [str(i) for i in left] == [kept]
        # Its games went with it.
        assert (
            conn.execute(
                text("SELECT count(*) FROM matches WHERE group_id = :g"), {"g": gid}
            ).scalar_one()
            == 0
        )


def test_the_app_cannot_purge(app_engine: Engine, people: People) -> None:
    user = people.user_id(people.new("Riley"))
    with as_user(app_engine, user) as conn, pytest.raises(Exception, match="permission denied"):
        conn.execute(text("SELECT app_purge_deleted_groups()"))
