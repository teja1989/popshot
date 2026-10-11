"""Admin actions (migration 0013, routes/admin_actions.py): making a member a crew's lead."""

from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, text

from popshot_api.routes.admin_actions import FRESH_SIGN_IN
from tests.db.conftest import (
    ADMIN,
    INSUFFICIENT_PRIVILEGE,
    Admins,
    People,
    as_user,
    create,
    sign_in,
    sqlstate_of,
)
from tests.db.test_games_api import join_and_approve

pytestmark = pytest.mark.db

REASON = "Casey asked support to hand over; they've moved away."


@pytest.fixture
def crew(admins: Admins) -> dict[str, Any]:
    casey = admins.new("Casey")
    group_id = create(admins, casey, "Thursday Smashers")["id"]
    sam = join_and_approve(admins, casey, group_id, "Sam")
    return {
        "group_id": group_id,
        "casey": casey,
        "casey_id": admins.user_id(casey),
        "sam": sam,
        "sam_id": admins.user_id(sam),
    }


def roles(owner_engine: Engine, group_id: str) -> dict[UUID, str]:
    with owner_engine.connect() as conn:
        rows = conn.execute(
            text("SELECT user_id, role::text FROM group_members WHERE group_id = :g"),
            {"g": group_id},
        ).all()
    return {r.user_id: r.role for r in rows}


def make_lead(admins: Admins, headers: dict[str, str], group_id: str, body: dict[str, Any]) -> Any:
    return admins.admin.post(f"/v1/admin/groups/{group_id}/lead", json=body, headers=headers)


def test_everyone_else_gets_not_found(admins: Admins, crew: dict[str, Any]) -> None:
    body = {"user_id": str(crew["sam_id"]), "reason": REASON}
    response = make_lead(admins, crew["casey"], crew["group_id"], body)
    assert (response.status_code, response.json()) == (404, {"detail": "Not Found"})


def test_changes_need_a_sign_in_from_the_last_15_minutes(
    admins: Admins, crew: dict[str, Any], owner_engine: Engine
) -> None:
    before = roles(owner_engine, crew["group_id"])
    stale = sign_in(admins, ADMIN.lower(), signed_in_ago=FRESH_SIGN_IN + 60)
    body = {"user_id": str(crew["sam_id"]), "reason": REASON}
    response = make_lead(admins, stale, crew["group_id"], body)
    assert (response.status_code, response.json()) == (
        403,
        {"detail": "Sign in again to make changes."},
    )
    # Still fine for looking.
    assert (
        admins.admin.get(f"/v1/admin/groups/{crew['group_id']}", headers=stale).status_code == 200
    )
    assert roles(owner_engine, crew["group_id"]) == before


def test_make_a_member_the_lead(admins: Admins, crew: dict[str, Any], owner_engine: Engine) -> None:
    boss = sign_in(admins, ADMIN.lower())
    body = {"user_id": str(crew["sam_id"]), "reason": f"  {REASON}  "}
    response = make_lead(admins, boss, crew["group_id"], body)
    assert response.status_code == 200, response.text
    assert response.json() == {"lead": str(crew["sam_id"]), "previous_lead": str(crew["casey_id"])}
    # Exactly one lead; the old one is a co-lead.
    assert roles(owner_engine, crew["group_id"]) == {
        crew["sam_id"]: "lead",
        crew["casey_id"]: "co_lead",
    }
    # Sam can now do what a lead does.
    rename = admins.client.patch(
        f"/v1/groups/{crew['group_id']}", json={"name": "Sam's Smashers"}, headers=crew["sam"]
    )
    assert rename.status_code == 200, rename.text
    # The crew's support history shows it, reason trimmed.
    detail = admins.admin.get(f"/v1/admin/groups/{crew['group_id']}", headers=boss).json()
    [action] = detail["actions"]
    assert (action["action"], action["admin_name"], action["target_name"], action["reason"]) == (
        "crew.lead_changed",
        "Admin Test",
        "Sam",
        REASON,
    )
    assert action["details"] == {"previous_lead": str(crew["casey_id"])}


@pytest.mark.parametrize(
    "body",
    [
        {"reason": REASON},
        {"user_id": "not-a-uuid", "reason": REASON},
        {"user_id": str(uuid4()), "reason": "   too short   "},
        {"user_id": str(uuid4()), "reason": "x" * 501},
        {"user_id": str(uuid4()), "reason": REASON, "extra": True},
    ],
)
def test_a_reason_is_required_and_checked(
    admins: Admins, crew: dict[str, Any], body: dict[str, Any]
) -> None:
    response = make_lead(admins, sign_in(admins, ADMIN.lower()), crew["group_id"], body)
    assert response.status_code == 422


def test_refusals(admins: Admins, crew: dict[str, Any], owner_engine: Engine) -> None:
    boss = sign_in(admins, ADMIN.lower())
    outsider = admins.user_id(admins.new("Jordan"))
    before = roles(owner_engine, crew["group_id"])

    def attempt(group_id: str, user_id: UUID) -> tuple[int, str]:
        response = make_lead(admins, boss, group_id, {"user_id": str(user_id), "reason": REASON})
        return response.status_code, response.json()["detail"]

    assert attempt(crew["group_id"], outsider) == (
        409,
        "Only an active member can be made the lead.",
    )
    assert attempt(crew["group_id"], crew["casey_id"]) == (409, "They're already the lead.")
    assert attempt(str(uuid4()), crew["sam_id"]) == (404, "No such crew.")
    # A deleted crew is left alone too.
    deleted = admins.client.delete(f"/v1/groups/{crew['group_id']}", headers=crew["casey"])
    assert deleted.status_code == 204
    assert attempt(crew["group_id"], crew["sam_id"]) == (404, "No such crew.")
    assert roles(owner_engine, crew["group_id"]) == before
    with owner_engine.connect() as conn:
        logged = conn.execute(
            text("SELECT count(*) FROM admin_actions WHERE group_id = :g"),
            {"g": crew["group_id"]},
        ).scalar_one()
    assert logged == 0


def test_only_the_admin_service_can_make_a_lead_and_nobody_edits_the_log(
    people: People, app_engine: Engine, admin_engine: Engine
) -> None:
    casey = people.new("Casey")
    casey_id = people.user_id(casey)
    group_id = create(people, casey)["id"]
    call = "SELECT * FROM app_admin_make_lead(:g, :u, :why)"
    params = {"g": group_id, "u": casey_id, "why": REASON}
    with as_user(app_engine, casey_id) as conn:
        assert sqlstate_of(conn, call, params) == INSUFFICIENT_PRIVILEGE
        assert (
            sqlstate_of(conn, "SELECT * FROM app_admin_group_actions(:g)", {"g": group_id})
            == INSUFFICIENT_PRIVILEGE
        )
    with as_user(admin_engine, casey_id) as conn:
        for statement in (
            "SELECT count(*) FROM admin_actions",
            "UPDATE admin_actions SET reason = 'rewritten history'",
            "DELETE FROM admin_actions",
        ):
            assert sqlstate_of(conn, statement) == INSUFFICIENT_PRIVILEGE, statement
        insert = (
            "INSERT INTO admin_actions (admin_user_id, action, reason) "
            "VALUES (:u, 'crew.lead_changed', 'a made-up entry')"
        )
        assert sqlstate_of(conn, insert, {"u": casey_id}) == INSUFFICIENT_PRIVILEGE
