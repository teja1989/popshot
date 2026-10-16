"""Feature switches and crew plans (migration 0027, routes/features.py): the access rule.

Each test makes its own throwaway features (test.f_<hex>), so nothing here depends on the
real ones, and removes them after.
"""

import itertools
import secrets
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import Connection, Engine, text

from tests.db.conftest import INSUFFICIENT_PRIVILEGE, People, as_user, create, sqlstate_of
from tests.db.test_games_api import join_and_approve

pytestmark = pytest.mark.db


@contextmanager
def owner(owner_engine: Engine) -> Iterator[Connection]:
    """As the tables' owner, which only migrations and the definer functions act as."""
    with owner_engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE popshot_owner"))
        yield conn


class Switches:
    def __init__(self, owner_engine: Engine) -> None:
        self.owner_engine = owner_engine
        self.made: list[str] = []

    def new(self, rollout: str = "off", needs_plan: str | None = None) -> str:
        key = f"test.f_{secrets.token_hex(6)}"
        with owner(self.owner_engine) as conn:
            conn.execute(
                text(
                    "INSERT INTO features (key, area, title, description, needs_plan, rollout) "
                    "VALUES (:k, 'play', 'Test', 'A switch for a test.', :p, :r)"
                ),
                {"k": key, "p": needs_plan, "r": rollout},
            )
        self.made.append(key)
        return key

    def set(self, key: str, **values: Any) -> None:
        assignments = ", ".join(f"{column} = :{column}" for column in values)
        with owner(self.owner_engine) as conn:
            conn.execute(
                text(f"UPDATE features SET {assignments} WHERE key = :k"), {**values, "k": key}
            )

    def list_crew(self, key: str, group_id: str) -> None:
        with owner(self.owner_engine) as conn:
            conn.execute(
                text("INSERT INTO feature_crews (feature_key, group_id) VALUES (:k, :g)"),
                {"k": key, "g": group_id},
            )

    def plan(self, group_id: str, starts: str, ends: str | None) -> None:
        """A plan starting and ending relative to now, e.g. '-1 day', '+1 day' or None."""
        with owner(self.owner_engine) as conn:
            conn.execute(
                text(
                    "INSERT INTO crew_plans (group_id, plan, source, starts_at, ends_at) "
                    "VALUES (:g, 'organizer', 'beta', now() + CAST(:s AS interval), "
                    "now() + CAST(:e AS interval))"
                ),
                {"g": group_id, "s": starts, "e": ends},
            )

    def cleanup(self) -> None:
        with owner(self.owner_engine) as conn:
            conn.execute(text("DELETE FROM features WHERE key = ANY(:k)"), {"k": self.made})


@pytest.fixture
def switches(owner_engine: Engine) -> Iterator[Switches]:
    made = Switches(owner_engine)
    yield made
    made.cleanup()


def is_on(app_engine: Engine, user_id: UUID, key: str, group_id: str) -> bool:
    with as_user(app_engine, user_id) as conn:
        on: bool = conn.execute(
            text("SELECT app_feature_on(:k, :g)"), {"k": key, "g": group_id}
        ).scalar_one()
    return on


PLANS: dict[str, tuple[str, str | None] | None] = {
    "none": None,
    "running": ("-1 day", None),
    "ended": ("-10 days", "-1 day"),
    "not_started": ("+1 day", None),
}


def test_the_rule(people: People, switches: Switches, app_engine: Engine) -> None:
    casey = people.new("Casey")
    me = people.user_id(casey)
    # One crew for each (on the list?, plan) pair.
    crews: dict[tuple[bool, str], str] = {}
    for listed, plan in itertools.product((False, True), PLANS):
        crews[(listed, plan)] = create(people, casey, f"Crew {listed} {plan}")["id"]
        if PLANS[plan] is not None:
            starts, ends = PLANS[plan]  # type: ignore[misc]
            switches.plan(crews[(listed, plan)], starts, ends)

    for rollout, needs_plan in itertools.product(("off", "crews", "everyone"), (None, "organizer")):
        key = switches.new(rollout, needs_plan)
        for (listed, plan), group_id in crews.items():
            if listed:
                switches.list_crew(key, group_id)
            if rollout == "crews":
                expected = listed
            elif rollout == "everyone":
                expected = needs_plan is None or plan == "running"
            else:
                expected = False
            case = (rollout, needs_plan, listed, plan)
            assert is_on(app_engine, me, key, group_id) is expected, case


def test_only_active_members_get_an_answer(
    people: People, switches: Switches, app_engine: Engine
) -> None:
    casey = people.new("Casey")
    group_id = create(people, casey)["id"]
    sam = join_and_approve(people, casey, group_id, "Sam")
    stranger = people.user_id(people.new("Robin"))
    key = switches.new("everyone")
    assert is_on(app_engine, people.user_id(sam), key, group_id)
    # Someone outside the crew can't find out what it has.
    assert not is_on(app_engine, stranger, key, group_id)
    with as_user(app_engine, None) as conn:
        assert not conn.execute(
            text("SELECT app_feature_on(:k, :g)"), {"k": key, "g": group_id}
        ).scalar_one()
    # Nor can someone who left.
    assert people.client.post(f"/v1/groups/{group_id}/leave", headers=sam).status_code == 204
    assert not is_on(app_engine, people.user_id(sam), key, group_id)
    # A deleted crew has nothing on.
    assert people.client.delete(f"/v1/groups/{group_id}", headers=casey).status_code == 204
    assert not is_on(app_engine, people.user_id(casey), key, group_id)


def test_unknown_features_are_off_and_changes_apply_at_once(
    people: People, switches: Switches, app_engine: Engine
) -> None:
    casey = people.new("Casey")
    me = people.user_id(casey)
    group_id = create(people, casey)["id"]
    assert not is_on(app_engine, me, "test.no_such_feature", group_id)
    key = switches.new("off")
    assert not is_on(app_engine, me, key, group_id)
    switches.set(key, rollout="everyone")
    assert is_on(app_engine, me, key, group_id)
    # Off beats a plan and the list.
    switches.list_crew(key, group_id)
    switches.plan(group_id, "-1 day", None)
    switches.set(key, rollout="off")
    assert not is_on(app_engine, me, key, group_id)


def test_my_features(people: People, switches: Switches, owner_engine: Engine) -> None:
    casey = people.new("Casey")
    mine = create(people, casey, "Mine")["id"]
    other = create(people, casey, "Other")["id"]
    beta = switches.new("crews")
    switches.list_crew(beta, mine)
    paid = switches.new("everyone", "organizer")
    switches.plan(other, "-1 day", None)
    body = people.client.get("/v1/me/features", headers=casey).json()
    assert beta in body["crews"][mine]
    assert beta not in body["crews"][other]
    assert paid in body["crews"][other]
    assert paid not in body["crews"][mine]
    assert {beta, paid} <= set(body["everywhere"])
    # The AI recap writer starts on for everyone.
    assert "recaps.ai" in body["crews"][mine]
    # Someone with no crews gets nothing about crews; only what's live anywhere, by key
    # (migration 0039), which includes beta now that a crew has it.
    loner = people.client.get("/v1/me/features", headers=people.new("Robin")).json()
    assert {k: v for k, v in loner.items() if k != "live"} == {
        "crews": {},
        "everywhere": [],
        "you": [],
    }
    with owner(owner_engine) as conn:
        expected = (
            conn.execute(
                text(
                    "SELECT key FROM features f WHERE rollout = 'everyone' OR (rollout = 'crews' "
                    "AND EXISTS (SELECT 1 FROM feature_crews c JOIN groups g ON g.id = c.group_id "
                    "AND g.deleted_at IS NULL WHERE c.feature_key = f.key)) ORDER BY key"
                )
            )
            .scalars()
            .all()
        )
    assert loner["live"] == list(expected)
    assert beta in loner["live"]
    assert people.client.get("/v1/me/features").status_code == 401


def test_only_the_functions_touch_the_tables(
    people: People, app_engine: Engine, admin_engine: Engine
) -> None:
    casey = people.new("Casey")
    me = people.user_id(casey)
    group_id = create(people, casey)["id"]
    for engine in (app_engine, admin_engine):
        with as_user(engine, me) as conn:
            for statement in (
                "SELECT count(*) FROM features",
                "SELECT count(*) FROM feature_crews",
                "SELECT count(*) FROM crew_plans",
                "UPDATE features SET rollout = 'everyone'",
                "DELETE FROM crew_plans",
            ):
                assert sqlstate_of(conn, statement) == INSUFFICIENT_PRIVILEGE, statement
            # The bare rule isn't granted to anyone, so no crew can be probed through it.
            assert (
                sqlstate_of(conn, "SELECT app_feature_allowed('recaps.ai', :g)", {"g": group_id})
                == INSUFFICIENT_PRIVILEGE
            )
    with as_user(app_engine, me) as conn:
        for call in (
            "SELECT * FROM app_admin_features()",
            "SELECT * FROM app_admin_crew_features(:g)",
            "SELECT app_admin_set_feature_rollout('recaps.ai', 'off', 'a reason long enough')",
            "SELECT app_admin_grant_plan(:g, 'organizer', 'comp', NULL, NULL, 'a long reason')",
        ):
            assert sqlstate_of(conn, call, {"g": group_id}) == INSUFFICIENT_PRIVILEGE, call
