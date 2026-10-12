"""Direct invites (routes/direct_invites.py, migration 0018), against the real database."""

from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import ProgrammingError

from popshot_api.routes.direct_invites import normalize_code, show_code
from tests.db.conftest import People, as_user, create
from tests.db.test_games_api import join_and_approve

pytestmark = pytest.mark.db

Headers = dict[str, str]
LOOKUPS_AN_HOUR = 20


def code_of(people: People, who: Headers) -> str:
    response = people.client.get("/v1/me/invite-code", headers=who)
    assert response.status_code == 200, response.text
    code: str = response.json()["code"]
    return code


def lookup(people: People, lead: Headers, group_id: str, code: str) -> Any:
    return people.client.post(
        f"/v1/groups/{group_id}/people/lookup", json={"code": code}, headers=lead
    )


def person(people: People, lead: Headers, group_id: str, code: str) -> dict[str, Any] | None:
    response = lookup(people, lead, group_id, code)
    assert response.status_code == 200, response.text
    found: dict[str, Any] | None = response.json()["person"]
    return found


def invite(people: People, lead: Headers, group_id: str, user_id: UUID | str) -> Any:
    return people.client.post(
        f"/v1/groups/{group_id}/direct-invites", json={"user_id": str(user_id)}, headers=lead
    )


def inbox(people: People, who: Headers) -> list[dict[str, Any]]:
    response = people.client.get("/v1/me/invites", headers=who)
    assert response.status_code == 200, response.text
    found: list[dict[str, Any]] = response.json()
    return found


def answer(people: People, who: Headers, invite_id: str, what: str) -> Any:
    return people.client.post(f"/v1/me/invites/{invite_id}", json={"answer": what}, headers=who)


def pending(people: People, lead: Headers, group_id: str) -> list[dict[str, Any]]:
    response = people.client.get(f"/v1/groups/{group_id}/direct-invites", headers=lead)
    assert response.status_code == 200, response.text
    found: list[dict[str, Any]] = response.json()
    return found


def invite_by_code(people: People, lead: Headers, group_id: str, who: Headers) -> UUID:
    found = person(people, lead, group_id, code_of(people, who))
    assert found is not None
    assert invite(people, lead, group_id, found["user_id"]).status_code == 201
    return UUID(found["user_id"])


@pytest.fixture
def crew(people: People) -> dict[str, Any]:
    """Casey leads Lunch Dinkers, with Sam as a member. Robin Hale is a stranger."""
    casey = people.new("Casey")
    group_id = create(people, casey, name="Lunch Dinkers")["id"]
    sam = join_and_approve(people, casey, group_id, "Sam")
    robin = people.new("Robin Hale")
    return {"group_id": group_id, "casey": casey, "sam": sam, "robin": robin}


def test_codes_read_easily_and_can_be_changed() -> None:
    assert normalize_code("k7m2-qx4p") == "K7M2QX4P"
    assert normalize_code(" K7M2 QX4P ") == "K7M2QX4P"
    # Letters people mix up read as the digits they look like.
    assert normalize_code("OILZ-0000") == "011Z0000"
    assert normalize_code("K7M2-QX4") is None
    assert normalize_code("K7M2-QX4U") is None  # U isn't used
    assert show_code("K7M2QX4P") == "K7M2-QX4P"


def test_your_code_stays_the_same_until_you_change_it(people: People, crew: dict[str, Any]) -> None:
    first = code_of(people, crew["robin"])
    assert normalize_code(first) is not None
    assert code_of(people, crew["robin"]) == first
    changed = people.client.post("/v1/me/invite-code", headers=crew["robin"]).json()["code"]
    assert changed != first
    assert code_of(people, crew["robin"]) == changed
    # The old code finds nobody now.
    assert person(people, crew["casey"], crew["group_id"], first) is None
    assert person(people, crew["casey"], crew["group_id"], changed) is not None


def test_a_lead_finds_someone_by_code_and_sees_only_a_first_name(
    people: People, crew: dict[str, Any]
) -> None:
    code = code_of(people, crew["robin"])
    found = lookup(people, crew["casey"], crew["group_id"], code.lower().replace("-", " "))
    assert found.status_code == 200, found.text
    body = found.json()["person"]
    assert body["display_name"] == "Robin"
    assert body["standing"] is None
    assert "Hale" not in found.text
    # Only leads and co-leads look codes up; outsiders don't learn the crew exists.
    assert lookup(people, crew["sam"], crew["group_id"], code).status_code == 403
    assert lookup(people, people.new("Riley"), crew["group_id"], code).status_code == 404
    # Your own code, a malformed one, or one nobody has: nobody.
    own = code_of(people, crew["casey"])
    for miss in (own, "nope", "0000-0000"):
        assert person(people, crew["casey"], crew["group_id"], miss) is None


def test_code_lookups_are_limited_each_hour(people: People, crew: dict[str, Any]) -> None:
    code = code_of(people, crew["robin"])
    for _ in range(LOOKUPS_AN_HOUR):
        assert person(people, crew["casey"], crew["group_id"], "0000-0000") is None
    # Wrong codes count too: even the right code waits now.
    limited = lookup(people, crew["casey"], crew["group_id"], code)
    assert limited.status_code == 429
    # Someone else's lookups are their own.
    other = people.new("Jo")
    other_group = create(people, other)["id"]
    assert person(people, other, other_group, code) is not None


def test_invite_by_code_then_accept_joins_the_crew(people: People, crew: dict[str, Any]) -> None:
    gid = crew["group_id"]
    robin_id = invite_by_code(people, crew["casey"], gid, crew["robin"])
    [waiting] = pending(people, crew["casey"], gid)
    assert waiting["user_id"] == str(robin_id)
    assert waiting["invited_by_name"] == "Casey"

    [mine] = inbox(people, crew["robin"])
    assert mine["group_name"] == "Lunch Dinkers"
    assert mine["invited_by_name"] == "Casey"
    assert mine["members"] == 2
    # Not in the crew until accepting.
    assert people.client.get(f"/v1/groups/{gid}", headers=crew["robin"]).status_code == 404

    accepted = answer(people, crew["robin"], mine["id"], "accept")
    assert accepted.status_code == 200, accepted.text
    assert accepted.json() == {"group_id": gid, "answer": "accept"}
    group = people.client.get(f"/v1/groups/{gid}", headers=crew["robin"])
    assert group.status_code == 200
    assert inbox(people, crew["robin"]) == []
    assert pending(people, crew["casey"], gid) == []
    # Answering twice: nothing open.
    assert answer(people, crew["robin"], mine["id"], "accept").status_code == 404


def test_only_people_you_found_can_be_invited(
    people: People, crew: dict[str, Any], app_engine: Engine
) -> None:
    gid = crew["group_id"]
    robin_id = people.user_id(crew["robin"])
    # Robin's ID without the code: nobody to invite.
    assert invite(people, crew["casey"], gid, robin_id).status_code == 404
    assert inbox(people, crew["robin"]) == []
    # Members can't invite.
    code = code_of(people, crew["robin"])
    assert person(people, crew["casey"], gid, code) is not None
    assert invite(people, crew["sam"], gid, robin_id).status_code == 403
    # Nor can you invite yourself, or someone already in.
    assert invite(people, crew["casey"], gid, people.user_id(crew["casey"])).status_code == 404
    already = invite(people, crew["casey"], gid, people.user_id(crew["sam"]))
    assert already.status_code == 409
    assert already.json()["detail"] == "They're already in the crew."


def test_sending_twice_makes_one_invite(people: People, crew: dict[str, Any]) -> None:
    gid = crew["group_id"]
    robin_id = invite_by_code(people, crew["casey"], gid, crew["robin"])
    assert invite(people, crew["casey"], gid, robin_id).status_code == 201
    assert len(pending(people, crew["casey"], gid)) == 1
    assert len(inbox(people, crew["robin"])) == 1


def test_known_people_are_crewmates_old_and_new(people: People, crew: dict[str, Any]) -> None:
    casey, gid = crew["casey"], crew["group_id"]
    # Casey's second crew, with Jo; then Jo leaves it. Jo is still someone Casey knows.
    other = create(people, casey, name="Sunday Smash")["id"]
    jo = join_and_approve(people, casey, other, "Jo Park")
    assert people.client.post(f"/v1/groups/{other}/leave", headers=jo).status_code == 204
    # Pat only asked to join and was never let in: not known.
    invite_link = people.client.post(f"/v1/groups/{other}/invites", json={}, headers=casey)
    pat = people.new("Pat")
    people.client.post("/v1/invites/join", json={"token": invite_link.json()["token"]}, headers=pat)

    known = people.client.get(f"/v1/groups/{gid}/people", headers=casey).json()
    assert {(p["display_name"], p["standing"]) for p in known} == {
        ("Sam", "member"),
        ("Jo Park", None),
    }
    assert [p["display_name"] for p in known] == ["Jo Park", "Sam"]
    found = people.client.get(f"/v1/groups/{gid}/people?q=PAR", headers=casey).json()
    assert [p["display_name"] for p in found] == ["Jo Park"]
    # No wildcards: the query is plain text.
    assert people.client.get(f"/v1/groups/{gid}/people?q=%25", headers=casey).json() == []
    assert people.client.get(f"/v1/groups/{gid}/people", headers=crew["sam"]).status_code == 403

    jo_id = next(p["user_id"] for p in known if p["display_name"] == "Jo Park")
    assert invite(people, casey, gid, jo_id).status_code == 201
    known = people.client.get(f"/v1/groups/{gid}/people?q=jo", headers=casey).json()
    assert known[0]["standing"] == "invited"


def test_declining_is_quiet_and_stops_reinvites_for_a_while(
    people: People, crew: dict[str, Any]
) -> None:
    gid = crew["group_id"]
    robin_id = invite_by_code(people, crew["casey"], gid, crew["robin"])
    [mine] = inbox(people, crew["robin"])
    assert answer(people, crew["robin"], mine["id"], "decline").status_code == 200
    # Gone from the lead's list; nothing says it was declined.
    assert pending(people, crew["casey"], gid) == []
    # Asking again right away: the crew sees "sent", Robin sees nothing.
    assert invite(people, crew["casey"], gid, robin_id).status_code == 201
    assert len(pending(people, crew["casey"], gid)) == 1
    assert inbox(people, crew["robin"]) == []


def test_blocking_a_crew_and_undoing_it(
    people: People, crew: dict[str, Any], owner_engine: Engine
) -> None:
    gid = crew["group_id"]
    robin_id = invite_by_code(people, crew["casey"], gid, crew["robin"])
    [mine] = inbox(people, crew["robin"])
    assert answer(people, crew["robin"], mine["id"], "block").status_code == 200
    blocks = people.client.get("/v1/me/invite-blocks", headers=crew["robin"]).json()
    assert [(b["group_id"], b["group_name"]) for b in blocks] == [(gid, "Lunch Dinkers")]
    # Even after the 14 quiet days, a blocked crew's invites never arrive.
    forget_decline(owner_engine, gid, robin_id)
    assert invite(people, crew["casey"], gid, robin_id).status_code == 201
    assert inbox(people, crew["robin"]) == []

    gone = people.client.delete(f"/v1/me/invite-blocks/{gid}", headers=crew["robin"])
    assert gone.status_code == 204
    assert people.client.get("/v1/me/invite-blocks", headers=crew["robin"]).json() == []
    assert (
        people.client.delete(f"/v1/me/invite-blocks/{gid}", headers=crew["robin"]).status_code
        == 404
    )


def forget_decline(owner_engine: Engine, group_id: str, user_id: UUID) -> None:
    """Move declines and open invites out of the way, as if 15 days had passed."""
    with owner_engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE popshot_owner"))
        conn.execute(
            text(
                "UPDATE direct_invites SET responded_at = now() - interval '15 days', "
                "status = CASE WHEN status IN ('pending', 'silenced') THEN 'expired' "
                "ELSE status END "
                "WHERE group_id = :g AND user_id = :u"
            ),
            {"g": group_id, "u": user_id},
        )


def test_expired_and_cancelled_invites_cant_be_accepted(
    people: People, crew: dict[str, Any], owner_engine: Engine
) -> None:
    gid = crew["group_id"]
    invite_by_code(people, crew["casey"], gid, crew["robin"])
    [mine] = inbox(people, crew["robin"])
    with owner_engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE popshot_owner"))
        conn.execute(
            text(
                "UPDATE direct_invites SET created_at = now() - interval '15 days', "
                "expires_at = now() - interval '1 day' WHERE id = :i"
            ),
            {"i": mine["id"]},
        )
    assert inbox(people, crew["robin"]) == []
    assert pending(people, crew["casey"], gid) == []
    assert answer(people, crew["robin"], mine["id"], "accept").status_code == 404

    # A fresh invite, then the lead takes it back.
    robin_id = invite_by_code(people, crew["casey"], gid, crew["robin"])
    [again] = pending(people, crew["casey"], gid)
    assert again["user_id"] == str(robin_id)
    deleted = people.client.delete(
        f"/v1/groups/{gid}/direct-invites/{again['id']}", headers=crew["casey"]
    )
    assert deleted.status_code == 204
    assert inbox(people, crew["robin"]) == []
    assert answer(people, crew["robin"], again["id"], "accept").status_code == 404


def test_crews_and_people_stay_apart(people: People, crew: dict[str, Any]) -> None:
    gid = crew["group_id"]
    invite_by_code(people, crew["casey"], gid, crew["robin"])
    [mine] = inbox(people, crew["robin"])
    [waiting] = pending(people, crew["casey"], gid)
    # Another crew's lead sees none of it and can't cancel it through their own crew.
    bo = people.new("Bo")
    bos = create(people, bo)["id"]
    assert pending(people, bo, bos) == []
    assert people.client.get(f"/v1/groups/{gid}/direct-invites", headers=bo).status_code == 404
    assert (
        people.client.delete(
            f"/v1/groups/{bos}/direct-invites/{waiting['id']}", headers=bo
        ).status_code
        == 404
    )
    # Nobody but Robin can answer Robin's invite.
    for other in (bo, crew["sam"], crew["casey"]):
        assert answer(people, other, mine["id"], "accept").status_code == 404
    assert len(inbox(people, crew["robin"])) == 1


def test_people_who_left_or_were_removed_can_be_invited_back(
    people: People, crew: dict[str, Any]
) -> None:
    casey, gid = crew["casey"], crew["group_id"]
    sam_id = people.user_id(crew["sam"])
    removed = people.client.patch(
        f"/v1/groups/{gid}/members/{sam_id}", json={"action": "remove"}, headers=casey
    )
    assert removed.status_code == 200, removed.text
    assert invite(people, casey, gid, sam_id).status_code == 201
    [mine] = inbox(people, crew["sam"])
    assert answer(people, crew["sam"], mine["id"], "accept").status_code == 200
    detail = people.client.get(f"/v1/groups/{gid}", headers=crew["sam"])
    assert detail.status_code == 200
    assert detail.json()["my_role"] == "member"


def test_a_join_request_turns_into_membership_on_accept(
    people: People, crew: dict[str, Any]
) -> None:
    casey, gid = crew["casey"], crew["group_id"]
    link = people.client.post(
        f"/v1/groups/{gid}/invites", json={"max_uses": 3}, headers=casey
    ).json()
    robin_id = invite_by_code(people, casey, gid, crew["robin"])
    joined = people.client.post(
        "/v1/invites/join", json={"token": link["token"]}, headers=crew["robin"]
    )
    assert joined.json()["status"] == "pending"
    # The open invite still works and lets Robin straight in.
    [mine] = inbox(people, crew["robin"])
    assert answer(people, crew["robin"], mine["id"], "accept").status_code == 200
    assert people.client.get(f"/v1/groups/{gid}", headers=crew["robin"]).status_code == 200
    # Asking to invite someone who's waiting on a request says so.
    pat = people.new("Pat")
    people.client.post("/v1/invites/join", json={"token": link["token"]}, headers=pat)
    lookup(people, casey, gid, code_of(people, pat))
    waiting = invite(people, casey, gid, people.user_id(pat))
    assert waiting.status_code == 409
    assert "asked to join" in waiting.json()["detail"]
    assert robin_id


def test_a_deleted_crews_invites_disappear(people: People, crew: dict[str, Any]) -> None:
    gid = crew["group_id"]
    invite_by_code(people, crew["casey"], gid, crew["robin"])
    [mine] = inbox(people, crew["robin"])
    assert people.client.delete(f"/v1/groups/{gid}", headers=crew["casey"]).status_code == 204
    assert inbox(people, crew["robin"]) == []
    assert answer(people, crew["robin"], mine["id"], "accept").status_code == 404


def test_the_app_role_cant_touch_the_tables(people: People, app_engine: Engine) -> None:
    riley = people.user_id(people.new("Riley"))
    for table in ("direct_invites", "invite_blocks", "invite_code_lookups"):
        with as_user(app_engine, riley) as conn, pytest.raises(ProgrammingError, match="denied"):
            conn.execute(text(f"SELECT 1 FROM {table} LIMIT 1"))
    for helper in ("app_knows(gen_random_uuid())", "app_invite_standing(NULL, NULL)"):
        with as_user(app_engine, riley) as conn, pytest.raises(ProgrammingError, match="denied"):
            conn.execute(text(f"SELECT {helper}"))
    # Codes are yours to set only through the API; you can't read anyone else's.
    with as_user(app_engine, riley) as conn:
        others = conn.execute(
            text("SELECT count(*) FROM users WHERE invite_code IS NOT NULL AND id <> :me"),
            {"me": riley},
        ).scalar_one()
    assert others == 0


def test_the_functions_check_roles_themselves(
    people: People, crew: dict[str, Any], app_engine: Engine
) -> None:
    """Even called directly (not through the API), a member who isn't a lead gets nothing."""
    gid = crew["group_id"]
    robin_id = invite_by_code(people, crew["casey"], gid, crew["robin"])
    code = normalize_code(code_of(people, crew["robin"]))
    sam = people.user_id(crew["sam"])
    with as_user(app_engine, sam) as conn:
        assert conn.execute(text("SELECT * FROM app_known_people(:g, '')"), {"g": gid}).all() == []
        assert (
            conn.execute(
                text("SELECT * FROM app_lookup_invite_code(:g, :c)"), {"g": gid, "c": code}
            ).all()
            == []
        )
        assert (
            conn.execute(text("SELECT * FROM app_group_direct_invites(:g)"), {"g": gid}).all() == []
        )
        assert (
            conn.execute(
                text("SELECT app_send_direct_invite(:g, :u)"), {"g": gid, "u": robin_id}
            ).scalar_one()
            == "not_found"
        )
        invite_id = inbox(people, crew["robin"])[0]["id"]
        assert (
            conn.execute(text("SELECT app_cancel_direct_invite(:i)"), {"i": invite_id}).scalar_one()
            is False
        )
