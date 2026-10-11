"""Invite links and member management end to end against the real database."""

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, text

from popshot_api.routes.invites import INVITE_DAYS, MAX_INVITE_USES, MAX_LIVE_INVITES
from tests.db.conftest import People, as_user, create

pytestmark = pytest.mark.db

Headers = dict[str, str]


def invite(people: People, headers: Headers, group_id: str, max_uses: int = 1) -> dict[str, Any]:
    response = people.client.post(
        f"/v1/groups/{group_id}/invites", json={"max_uses": max_uses}, headers=headers
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def join(people: People, headers: Headers, token: str) -> Any:
    return people.client.post("/v1/invites/join", json={"token": token}, headers=headers)


def preview(people: People, headers: Headers, token: str) -> Any:
    return people.client.post("/v1/invites/preview", json={"token": token}, headers=headers)


def change(people: People, headers: Headers, group_id: str, user_id: UUID, action: str) -> Any:
    return people.client.patch(
        f"/v1/groups/{group_id}/members/{user_id}", json={"action": action}, headers=headers
    )


def members(people: People, headers: Headers, group_id: str) -> list[tuple[str, str, str]]:
    detail = people.client.get(f"/v1/groups/{group_id}", headers=headers).json()
    return [(m["display_name"], m["role"], m["status"]) for m in detail["members"]]


def crew(people: People) -> tuple[str, Headers, Headers]:
    """A group led by Casey, with Sam as an approved member."""
    casey, sam = people.new("Casey"), people.new("Sam")
    group_id = create(people, casey)["id"]
    assert join(people, sam, invite(people, casey, group_id)["token"]).status_code == 200
    assert change(people, casey, group_id, people.user_id(sam), "approve").status_code == 200
    return group_id, casey, sam


def test_lead_makes_a_link_and_only_its_hash_is_stored(people: People, app_engine: Engine) -> None:
    casey = people.new("Casey")
    group_id = create(people, casey)["id"]
    made = invite(people, casey, group_id, max_uses=5)

    assert len(made["token"]) == 43
    assert (made["max_uses"], made["use_count"], made["created_by_name"]) == (5, 0, "Casey")
    expires = datetime.fromisoformat(made["expires_at"])
    expected = datetime.now(UTC) + timedelta(days=INVITE_DAYS)
    assert abs(expires - expected) < timedelta(minutes=5)

    with as_user(app_engine, people.user_id(casey)) as conn:
        stored = conn.execute(
            text("SELECT token_hash, requires_approval FROM group_invites WHERE id = :id"),
            {"id": made["id"]},
        ).one()
    assert bytes(stored.token_hash) == hashlib.sha256(made["token"].encode()).digest()
    assert stored.requires_approval is True

    # The list never includes tokens.
    listed = people.client.get(f"/v1/groups/{group_id}/invites", headers=casey).json()
    assert [i["id"] for i in listed] == [made["id"]]
    assert "token" not in listed[0]


@pytest.mark.parametrize("body", [{"max_uses": 0}, {"max_uses": MAX_INVITE_USES + 1}, {"x": 1}])
def test_rejects_bad_invite_settings(people: People, body: dict[str, Any]) -> None:
    casey = people.new("Casey")
    group_id = create(people, casey)["id"]
    response = people.client.post(f"/v1/groups/{group_id}/invites", json=body, headers=casey)
    assert response.status_code == 422


def test_only_admins_manage_links(people: People) -> None:
    group_id, casey, sam = crew(people)
    outsider = people.new("Jordan")
    made = invite(people, casey, group_id)
    path = f"/v1/groups/{group_id}/invites"

    assert people.client.post(path, json={}, headers=sam).status_code == 403
    assert people.client.get(path, headers=sam).status_code == 403
    assert people.client.delete(f"{path}/{made['id']}", headers=sam).status_code == 403
    for response in (
        people.client.post(path, json={}, headers=outsider),
        people.client.get(path, headers=outsider),
        people.client.delete(f"{path}/{made['id']}", headers=outsider),
        people.client.post(f"/v1/groups/{uuid4()}/invites", json={}, headers=outsider),
    ):
        assert response.status_code == 404


def test_caps_open_links(people: People) -> None:
    casey = people.new("Casey")
    group_id = create(people, casey)["id"]
    made = [invite(people, casey, group_id) for _ in range(MAX_LIVE_INVITES)]
    path = f"/v1/groups/{group_id}/invites"
    assert people.client.post(path, json={}, headers=casey).status_code == 409
    # Cancelling one frees a slot.
    assert people.client.delete(f"{path}/{made[0]['id']}", headers=casey).status_code == 204
    invite(people, casey, group_id)


def test_preview_shows_the_group_but_not_its_id(people: People) -> None:
    casey, riley = people.new("Casey"), people.new("Riley")
    group_id = create(people, casey, "Tuesday Dinkers")["id"]
    token = invite(people, casey, group_id)["token"]

    response = preview(people, riley, token)
    assert response.status_code == 200
    assert response.json() == {
        "group_name": "Tuesday Dinkers",
        "invited_by": "Casey",
        "group_id": None,
        "my_status": None,
    }
    # Looking doesn't use the link up.
    assert preview(people, riley, token).status_code == 200
    # Someone already in the group gets its ID, to go straight there.
    assert preview(people, casey, token).json()["group_id"] == group_id


@pytest.mark.parametrize("token", ["", "short", "x" * 43 + "!", "a" * 64, "é" * 43])
def test_malformed_tokens_are_the_same_404(people: People, token: str) -> None:
    riley = people.new("Riley")
    for response in (preview(people, riley, token), join(people, riley, token)):
        assert response.status_code == 404
        assert response.json()["detail"].startswith("This invite link isn't valid")


def test_unknown_token_is_404(people: People) -> None:
    riley = people.new("Riley")
    token = "A" * 43
    assert preview(people, riley, token).status_code == 404
    assert join(people, riley, token).status_code == 404


def test_too_long_token_is_rejected_before_hashing(people: People) -> None:
    response = join(people, people.new("Riley"), "a" * 65)
    assert response.status_code == 422


def test_joining_waits_for_approval_then_the_lead_lets_you_in(
    people: People, app_engine: Engine
) -> None:
    casey, riley = people.new("Casey"), people.new("Riley")
    group_id = create(people, casey)["id"]
    token = invite(people, casey, group_id)["token"]

    joined = join(people, riley, token)
    assert joined.status_code == 200
    assert joined.json() == {"group_id": group_id, "status": "pending"}
    # Joining again changes nothing and the link stays used once.
    assert join(people, riley, token).json() == {"group_id": group_id, "status": "pending"}
    waiting = people.client.get(f"/v1/groups/{group_id}", headers=riley).json()
    assert (waiting["my_status"], waiting["members"]) == ("pending", [])
    assert ("Riley", "member", "pending") in members(people, casey, group_id)

    riley_id = people.user_id(riley)
    response = change(people, casey, group_id, riley_id, "approve")
    assert response.status_code == 200
    assert ("Riley", "member", "active") in [
        (m["display_name"], m["role"], m["status"]) for m in response.json()["members"]
    ]
    assert people.client.get(f"/v1/groups/{group_id}", headers=riley).json()["my_status"] == (
        "active"
    )

    with as_user(app_engine, people.user_id(casey)) as conn:
        player = conn.execute(
            text("SELECT display_name FROM players WHERE group_id = :g AND user_id = :u"),
            {"g": group_id, "u": riley_id},
        ).scalar_one()
        actions = conn.execute(
            text("SELECT action FROM audit_log WHERE group_id = :g ORDER BY id"),
            {"g": group_id},
        ).scalars()
        assert list(actions) == ["invite.created", "member.approved"]
    assert player == "Riley"


def test_a_link_is_used_up_after_its_uses(people: People) -> None:
    casey = people.new("Casey")
    group_id = create(people, casey)["id"]
    made = invite(people, casey, group_id, max_uses=2)
    first, second, third = people.new("A"), people.new("B"), people.new("C")
    assert join(people, first, made["token"]).status_code == 200
    listed = people.client.get(f"/v1/groups/{group_id}/invites", headers=casey).json()
    assert listed[0]["use_count"] == 1
    assert join(people, second, made["token"]).status_code == 200
    assert join(people, third, made["token"]).status_code == 404
    assert preview(people, third, made["token"]).status_code == 404
    # A used-up link drops off the list.
    assert people.client.get(f"/v1/groups/{group_id}/invites", headers=casey).json() == []


def test_cancelled_link_stops_working(people: People) -> None:
    casey, riley = people.new("Casey"), people.new("Riley")
    group_id = create(people, casey)["id"]
    made = invite(people, casey, group_id, max_uses=3)
    path = f"/v1/groups/{group_id}/invites/{made['id']}"
    assert people.client.delete(path, headers=casey).status_code == 204
    assert people.client.delete(path, headers=casey).status_code == 404
    assert join(people, riley, made["token"]).status_code == 404
    assert people.client.get(f"/v1/groups/{group_id}/invites", headers=casey).json() == []


def test_cannot_cancel_another_groups_link(people: People) -> None:
    casey, sam = people.new("Casey"), people.new("Sam")
    mine = create(people, casey)["id"]
    theirs = create(people, sam)["id"]
    their_link = invite(people, sam, theirs)
    response = people.client.delete(f"/v1/groups/{mine}/invites/{their_link['id']}", headers=casey)
    assert response.status_code == 404
    assert len(people.client.get(f"/v1/groups/{theirs}/invites", headers=sam).json()) == 1


def test_declined_person_cant_rejoin_or_see_the_group(people: People) -> None:
    casey, riley = people.new("Casey"), people.new("Riley")
    group_id = create(people, casey)["id"]
    join(people, riley, invite(people, casey, group_id)["token"])
    assert change(people, casey, group_id, people.user_id(riley), "decline").status_code == 200
    assert ("Riley", "member", "pending") not in members(people, casey, group_id)
    assert people.client.get(f"/v1/groups/{group_id}", headers=riley).status_code == 404

    token = invite(people, casey, group_id)["token"]
    assert preview(people, riley, token).json()["group_id"] is None
    assert preview(people, riley, token).json()["my_status"] == "removed"
    assert join(people, riley, token).json() == {"group_id": None, "status": "removed"}


def test_lead_promotes_and_demotes_a_co_lead(people: People) -> None:
    group_id, casey, sam = crew(people)
    sam_id = people.user_id(sam)
    assert change(people, casey, group_id, sam_id, "make_co_lead").status_code == 200
    assert ("Sam", "co_lead", "active") in members(people, casey, group_id)

    # A co-lead can invite and approve.
    riley = people.new("Riley")
    join(people, riley, invite(people, sam, group_id)["token"])
    assert change(people, sam, group_id, people.user_id(riley), "approve").status_code == 200

    assert change(people, casey, group_id, sam_id, "make_member").status_code == 200
    assert ("Sam", "member", "active") in members(people, casey, group_id)
    assert people.client.get(f"/v1/groups/{group_id}/invites", headers=sam).status_code == 403


def test_what_a_co_lead_cannot_do(people: People) -> None:
    group_id, casey, sam = crew(people)
    alex = people.new("Alex")
    join(people, alex, invite(people, casey, group_id)["token"])
    alex_id = people.user_id(alex)
    change(people, casey, group_id, alex_id, "approve")
    for headers in (sam, alex):
        change(people, casey, group_id, people.user_id(headers), "make_co_lead")

    casey_id = people.user_id(casey)
    # Co-leads can't promote, demote or remove each other, or touch the lead.
    assert change(people, sam, group_id, alex_id, "make_member").status_code == 403
    assert change(people, sam, group_id, alex_id, "remove").status_code == 403
    for action in ("remove", "make_member", "make_co_lead"):
        assert change(people, sam, group_id, casey_id, action).status_code == 403
    assert ("Casey", "lead", "active") in members(people, casey, group_id)
    assert ("Alex", "co_lead", "active") in members(people, casey, group_id)


def test_plain_members_and_outsiders_cannot_manage(people: People) -> None:
    group_id, casey, sam = crew(people)
    riley = people.new("Riley")
    join(people, riley, invite(people, casey, group_id)["token"])
    riley_id = people.user_id(riley)
    assert change(people, sam, group_id, riley_id, "approve").status_code == 403
    outsider = people.new("Jordan")
    assert change(people, outsider, group_id, riley_id, "approve").status_code == 404
    # Pending people can't manage either.
    assert change(people, riley, group_id, people.user_id(sam), "remove").status_code == 404
    assert ("Riley", "member", "pending") in members(people, casey, group_id)


def test_lead_cannot_change_themselves(people: People) -> None:
    group_id, casey, _ = crew(people)
    for action in ("remove", "make_member"):
        assert change(people, casey, group_id, people.user_id(casey), action).status_code == 409


def test_actions_must_fit_the_members_state(people: People) -> None:
    group_id, casey, sam = crew(people)
    sam_id = people.user_id(sam)
    assert change(people, casey, group_id, sam_id, "approve").status_code == 409
    assert change(people, casey, group_id, sam_id, "decline").status_code == 409
    riley = people.new("Riley")
    join(people, riley, invite(people, casey, group_id)["token"])
    riley_id = people.user_id(riley)
    assert change(people, casey, group_id, riley_id, "make_co_lead").status_code == 409
    assert change(people, casey, group_id, riley_id, "remove").status_code == 409
    assert change(people, casey, group_id, uuid4(), "approve").status_code == 404
    bad = people.client.patch(
        f"/v1/groups/{group_id}/members/{riley_id}", json={"action": "make_owner"}, headers=casey
    )
    assert bad.status_code == 422


def test_removed_member_loses_access(people: People) -> None:
    group_id, casey, sam = crew(people)
    assert change(people, casey, group_id, people.user_id(sam), "remove").status_code == 200
    assert people.client.get(f"/v1/groups/{group_id}", headers=sam).status_code == 404
    assert people.client.get("/v1/groups", headers=sam).json() == []
    # Removing again: they're not a member any more.
    assert change(people, casey, group_id, people.user_id(sam), "remove").status_code == 404


def test_cannot_manage_members_of_another_group(people: People) -> None:
    group_id, _, sam = crew(people)
    jordan = people.new("Jordan")
    create(people, jordan)
    assert change(people, jordan, group_id, people.user_id(sam), "remove").status_code == 404
