"""Admin: feature switches and crew plans (routes/admin_features.py, migration 0027)."""

import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import Engine, text

from popshot_api.routes.admin_actions import FRESH_SIGN_IN
from tests.db.conftest import ADMIN, Admins, create, sign_in
from tests.db.test_features import Switches, owner

pytestmark = pytest.mark.db

REASON = "Beta for the Thursday crew, as agreed."


@pytest.fixture
def switches(owner_engine: Engine) -> Iterator[Switches]:
    made = Switches(owner_engine)
    yield made
    made.cleanup()


@pytest.fixture
def boss(admins: Admins) -> dict[str, str]:
    return sign_in(admins, ADMIN.lower())


def logged(owner_engine: Engine, action: str, **match: str) -> list[dict[str, Any]]:
    with owner(owner_engine) as conn:
        rows = conn.execute(
            text(
                "SELECT reason, details FROM admin_actions WHERE action = :a "
                "AND details @> CAST(:m AS jsonb) ORDER BY id"
            ),
            {"a": action, "m": json.dumps(match)},
        ).all()
    return [{"reason": r.reason, "details": r.details} for r in rows]


def test_everyone_else_gets_not_found(admins: Admins, switches: Switches) -> None:
    casey = admins.new("Casey")
    key = switches.new()
    for method, path, body in (
        ("GET", "/v1/admin/features", None),
        ("GET", "/v1/admin/plans", None),
        ("PUT", f"/v1/admin/features/{key}/rollout", {"rollout": "everyone", "reason": REASON}),
    ):
        response = admins.admin.request(method, path, json=body, headers=casey)
        assert (response.status_code, response.json()) == (404, {"detail": "Not Found"}), path


def test_changes_need_a_recent_sign_in_and_a_reason(
    admins: Admins, switches: Switches, owner_engine: Engine
) -> None:
    key = switches.new()
    stale = sign_in(admins, ADMIN.lower(), signed_in_ago=FRESH_SIGN_IN + 60)
    path = f"/v1/admin/features/{key}/rollout"
    response = admins.admin.put(path, json={"rollout": "everyone", "reason": REASON}, headers=stale)
    assert response.status_code == 403
    # Looking is still fine.
    assert admins.admin.get("/v1/admin/features", headers=stale).status_code == 200
    boss = sign_in(admins, ADMIN.lower())
    for body in (
        {"rollout": "everyone"},
        {"rollout": "everyone", "reason": "too short"},
        {"rollout": "sometimes", "reason": REASON},
        {"rollout": "everyone", "reason": REASON, "extra": 1},
    ):
        assert admins.admin.put(path, json=body, headers=boss).status_code == 422, body
    assert logged(owner_engine, "feature.rollout", feature=key) == []


def test_rollout_and_plan_are_logged_and_apply_at_once(
    admins: Admins, switches: Switches, owner_engine: Engine, boss: dict[str, str]
) -> None:
    casey = admins.new("Casey")
    group_id = create(admins, casey)["id"]
    key = switches.new()

    def mine() -> list[str]:
        crews: dict[str, list[str]] = admins.client.get("/v1/me/features", headers=casey).json()[
            "crews"
        ]
        return crews.get(group_id, [])

    assert key not in mine()
    path = f"/v1/admin/features/{key}"
    put = admins.admin.put(
        f"{path}/rollout", json={"rollout": "everyone", "reason": f"  {REASON} "}, headers=boss
    )
    assert put.status_code == 204, put.text
    assert key in mine()
    # The same again changes nothing and isn't logged twice.
    again = admins.admin.put(
        f"{path}/rollout", json={"rollout": "everyone", "reason": REASON}, headers=boss
    )
    assert again.status_code == 204
    assert logged(owner_engine, "feature.rollout", feature=key) == [
        {"reason": REASON, "details": {"feature": key, "before": "off", "after": "everyone"}}
    ]

    # Organizer only: Casey's crew has no plan, so it's gone.
    paid = admins.admin.put(
        f"{path}/plan", json={"needs_plan": "organizer", "reason": REASON}, headers=boss
    )
    assert paid.status_code == 204
    assert key not in mine()
    assert logged(owner_engine, "feature.plan", feature=key)[0]["details"] == {
        "feature": key,
        "before": None,
        "after": "organizer",
    }
    listed = {f["key"]: f for f in admins.admin.get("/v1/admin/features", headers=boss).json()}
    assert listed[key]["rollout"] == "everyone"
    assert listed[key]["needs_plan"] == "organizer"
    assert listed[key]["updated_by"] == "Admin Test"
    assert listed["recaps.ai"]["area"] == "recaps"

    missing = admins.admin.put(
        "/v1/admin/features/test.nope/rollout",
        json={"rollout": "off", "reason": REASON},
        headers=boss,
    )
    assert (missing.status_code, missing.json()["detail"]) == (404, "No such feature.")


def test_a_beta_list(
    admins: Admins, switches: Switches, owner_engine: Engine, boss: dict[str, str]
) -> None:
    casey = admins.new("Casey")
    group_id = create(admins, casey, "Thursday Smashers")["id"]
    key = switches.new("crews", "organizer")
    path = f"/v1/admin/features/{key}/crews/{group_id}"
    assert admins.admin.post(path, json={"reason": REASON}, headers=boss).status_code == 204
    crews = admins.admin.get(f"/v1/admin/features/{key}/crews", headers=boss).json()
    assert [(c["group_id"], c["name"]) for c in crews] == [(group_id, "Thursday Smashers")]
    # On the list, it's on even without a plan.
    access = admins.admin.get(f"/v1/admin/groups/{group_id}/access", headers=boss).json()
    assert key in access["features"]
    assert key in admins.client.get("/v1/me/features", headers=casey).json()["crews"][group_id]

    removed = admins.admin.post(f"{path}/remove", json={"reason": REASON}, headers=boss)
    assert removed.status_code == 204
    assert key not in admins.client.get("/v1/me/features", headers=casey).json()["crews"][group_id]
    assert [
        e["details"]["after"] for e in logged(owner_engine, "feature.crew_add", feature=key)
    ] == [True]
    assert [
        e["details"]["after"] for e in logged(owner_engine, "feature.crew_remove", feature=key)
    ] == [False]
    unknown = admins.admin.post(
        f"/v1/admin/features/{key}/crews/00000000-0000-0000-0000-000000000000",
        json={"reason": REASON},
        headers=boss,
    )
    assert (unknown.status_code, unknown.json()["detail"]) == (404, "No such crew.")


def test_plans_grant_change_and_end(
    admins: Admins, switches: Switches, owner_engine: Engine, boss: dict[str, str]
) -> None:
    casey = admins.new("Casey")
    group_id = create(admins, casey)["id"]
    key = switches.new("everyone", "organizer")
    path = f"/v1/admin/groups/{group_id}/plans/organizer"

    def on() -> bool:
        crews = admins.client.get("/v1/me/features", headers=casey).json()["crews"]
        return key in crews.get(group_id, [])

    past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    bad = admins.admin.put(
        path, json={"source": "comp", "ends_at": past, "reason": REASON}, headers=boss
    )
    assert (bad.status_code, bad.json()["detail"]) == (422, "The end has to be in the future.")
    assert not on()

    granted = admins.admin.put(
        path, json={"source": "beta", "note": "Founding crew", "reason": REASON}, headers=boss
    )
    assert granted.status_code == 204, granted.text
    assert on()
    [plan] = admins.admin.get(f"/v1/admin/groups/{group_id}/access", headers=boss).json()["plans"]
    assert (plan["source"], plan["ends_at"], plan["note"]) == ("beta", None, "Founding crew")
    assert any(
        p["group_id"] == group_id for p in admins.admin.get("/v1/admin/plans", headers=boss).json()
    )

    # Changing it keeps when it started.
    later = (datetime.now(UTC) + timedelta(days=30)).isoformat()
    changed = admins.admin.put(
        path, json={"source": "comp", "ends_at": later, "reason": REASON}, headers=boss
    )
    assert changed.status_code == 204
    [after] = admins.admin.get(f"/v1/admin/groups/{group_id}/access", headers=boss).json()["plans"]
    assert after["starts_at"] == plan["starts_at"]
    assert after["source"] == "comp"

    ended = admins.admin.post(f"{path}/end", json={"reason": REASON}, headers=boss)
    assert ended.status_code == 204
    assert not on()
    again = admins.admin.post(f"{path}/end", json={"reason": REASON}, headers=boss)
    assert (again.status_code, again.json()["detail"]) == (
        404,
        "This crew has no running plan to end.",
    )
    with owner(owner_engine) as conn:
        actions = conn.execute(
            text("SELECT action FROM admin_actions WHERE group_id = :g ORDER BY id"),
            {"g": group_id},
        ).scalars()
        assert list(actions) == ["plan.grant", "plan.grant", "plan.end"]
