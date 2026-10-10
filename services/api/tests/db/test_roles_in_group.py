"""What each kind of person can do inside a group: lead, member, pending, removed."""

import pytest
from sqlalchemy import Connection, Engine, text

from tests.db.conftest import (
    INSUFFICIENT_PRIVILEGE,
    Seed,
    as_user,
    new_token_hash,
    set_user,
    sqlstate_of,
)

pytestmark = pytest.mark.db


def _count(engine: Engine, user: object, sql: str, **params: object) -> int:
    with as_user(engine, user) as conn:  # type: ignore[arg-type]
        value: int = conn.execute(text(sql), params).scalar_one()
    return value


def test_member_in_two_groups_sees_both(app_engine: Engine, seed: Seed) -> None:
    with as_user(app_engine, seed.dave) as conn:
        groups = set(conn.execute(text("SELECT id FROM groups")).scalars())
        matches = set(conn.execute(text("SELECT id FROM matches")).scalars())
    assert groups == {seed.group_a, seed.group_b}
    assert matches == {seed.match_a, seed.match_b}


def test_plain_member_cannot_administer(app_engine: Engine, seed: Seed) -> None:
    with as_user(app_engine, seed.carol) as conn:
        renamed = conn.execute(
            text("UPDATE groups SET name = 'Carol rules' WHERE id = :g"), {"g": seed.group_a}
        )
        assert renamed.rowcount == 0
        promoted = conn.execute(
            text("UPDATE group_members SET role = 'lead' WHERE group_id = :g AND user_id = :u"),
            {"g": seed.group_a, "u": seed.dave},
        )
        assert promoted.rowcount == 0
        assert conn.execute(text("SELECT count(*) FROM group_invites")).scalar_one() == 0
        assert conn.execute(text("SELECT count(*) FROM audit_log")).scalar_one() == 0
        assert (
            sqlstate_of(
                conn,
                "INSERT INTO group_invites (group_id, token_hash, created_by, expires_at) "
                "VALUES (:g, :h, :u, now() + interval '1 day')",
                {"g": seed.group_a, "h": new_token_hash(), "u": seed.carol},
            )
            == INSUFFICIENT_PRIVILEGE
        )
        assert (
            conn.execute(text("DELETE FROM groups WHERE id = :g"), {"g": seed.group_a}).rowcount
            == 0
        )


def test_member_cannot_promote_themselves(app_engine: Engine, seed: Seed) -> None:
    sql = "UPDATE group_members SET role = :r WHERE group_id = :g AND user_id = :u"
    with as_user(app_engine, seed.carol) as conn:
        params = {"g": seed.group_a, "u": seed.carol}
        assert sqlstate_of(conn, sql, {**params, "r": "lead"}) == INSUFFICIENT_PRIVILEGE
        assert sqlstate_of(conn, sql, {**params, "r": "co_lead"}) == INSUFFICIENT_PRIVILEGE


def test_member_can_leave(app_engine: Engine, seed: Seed) -> None:
    with as_user(app_engine, seed.carol) as conn:
        left = conn.execute(
            text(
                "UPDATE group_members SET status = 'removed' WHERE group_id = :g AND user_id = :u"
            ),
            {"g": seed.group_a, "u": seed.carol},
        )
        assert left.rowcount == 1
        # Once removed, the group is gone from view in the same transaction.
        assert conn.execute(text("SELECT count(*) FROM matches")).scalar_one() == 0


def test_co_lead_and_lead_can_administer(app_engine: Engine, seed: Seed) -> None:
    with as_user(app_engine, seed.alice) as conn:
        conn.execute(
            text("UPDATE group_members SET role = 'co_lead' WHERE group_id = :g AND user_id = :u"),
            {"g": seed.group_a, "u": seed.carol},
        )
        conn.execute(text("SELECT set_config('app.user_id', :u, true)"), {"u": str(seed.carol)})
        renamed = conn.execute(
            text("UPDATE groups SET name = 'Tuesday Crew!' WHERE id = :g"), {"g": seed.group_a}
        )
        assert renamed.rowcount == 1
        assert conn.execute(text("SELECT count(*) FROM audit_log")).scalar_one() == 1
        # Only the lead can delete the group.
        assert (
            conn.execute(text("DELETE FROM groups WHERE id = :g"), {"g": seed.group_a}).rowcount
            == 0
        )


class TestCoLead:
    @staticmethod
    def _make_carol_co_lead(conn: Connection, seed: Seed) -> None:
        set_user(conn, seed.alice)
        conn.execute(
            text("UPDATE group_members SET role = 'co_lead' WHERE group_id = :g AND user_id = :u"),
            {"g": seed.group_a, "u": seed.carol},
        )
        set_user(conn, seed.carol)

    def test_can_approve_and_remove_plain_members(self, app_engine: Engine, seed: Seed) -> None:
        with as_user(app_engine, None) as conn:
            self._make_carol_co_lead(conn, seed)
            sql = "UPDATE group_members SET status = :s WHERE group_id = :g AND user_id = :u"
            approved = conn.execute(text(sql), {"s": "active", "g": seed.group_a, "u": seed.erin})
            assert approved.rowcount == 1
            removed = conn.execute(text(sql), {"s": "removed", "g": seed.group_a, "u": seed.dave})
            assert removed.rowcount == 1

    def test_cannot_touch_the_lead_or_promote(self, app_engine: Engine, seed: Seed) -> None:
        with as_user(app_engine, None) as conn:
            self._make_carol_co_lead(conn, seed)
            remove_lead = conn.execute(
                text(
                    "UPDATE group_members SET status = 'removed' "
                    "WHERE group_id = :g AND user_id = :u"
                ),
                {"g": seed.group_a, "u": seed.alice},
            )
            assert remove_lead.rowcount == 0
            promote = "UPDATE group_members SET role = :r WHERE group_id = :g AND user_id = :u"
            for target in (seed.carol, seed.dave):
                for new_role in ("lead", "co_lead"):
                    params = {"r": new_role, "g": seed.group_a, "u": target}
                    state = sqlstate_of(conn, promote, params)
                    # Own row: no policy matches the old row, so 0 rows; others: CHECK fails.
                    if state is None:
                        assert conn.execute(text(promote), params).rowcount == 0
                    else:
                        assert state == INSUFFICIENT_PRIVILEGE
            set_user(conn, seed.alice)
            roles: dict[object, str] = dict(
                conn.execute(
                    text("SELECT user_id, role FROM group_members WHERE group_id = :g"),
                    {"g": seed.group_a},
                ).all()
            )
            assert roles[seed.alice] == "lead"
            assert roles[seed.carol] == "co_lead"
            assert roles[seed.dave] == "member"


def test_lead_can_delete_group(app_engine: Engine, seed: Seed) -> None:
    with as_user(app_engine, seed.alice) as conn:
        deleted = conn.execute(text("DELETE FROM groups WHERE id = :g"), {"g": seed.group_a})
        assert deleted.rowcount == 1
        assert conn.execute(text("SELECT count(*) FROM matches")).scalar_one() == 0


def test_pending_member_sees_group_name_and_own_row_only(app_engine: Engine, seed: Seed) -> None:
    with as_user(app_engine, seed.erin) as conn:
        assert set(conn.execute(text("SELECT id FROM groups")).scalars()) == {seed.group_a}
        members = list(conn.execute(text("SELECT user_id, status FROM group_members")))
        assert [(m.user_id, m.status) for m in members] == [(seed.erin, "pending")]
        for table in ("players", "matches", "match_games", "ratings", "audit_log"):
            assert conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one() == 0


def test_removed_member_sees_nothing(app_engine: Engine, seed: Seed) -> None:
    with as_user(app_engine, seed.frank) as conn:
        assert conn.execute(text("SELECT count(*) FROM groups")).scalar_one() == 0
        assert conn.execute(text("SELECT count(*) FROM matches")).scalar_one() == 0
        # Can't rejoin by editing their own row.
        rejoin = "UPDATE group_members SET status = 'active' WHERE group_id = :g AND user_id = :u"
        params = {"g": seed.group_a, "u": seed.frank}
        assert sqlstate_of(conn, rejoin, params) == INSUFFICIENT_PRIVILEGE


def test_lead_approves_pending_member(app_engine: Engine, seed: Seed) -> None:
    with as_user(app_engine, seed.alice) as conn:
        approved = conn.execute(
            text("UPDATE group_members SET status = 'active' WHERE group_id = :g AND user_id = :u"),
            {"g": seed.group_a, "u": seed.erin},
        )
        assert approved.rowcount == 1


def test_matches_must_be_entered_as_yourself(app_engine: Engine, seed: Seed) -> None:
    with as_user(app_engine, seed.carol) as conn:
        state = sqlstate_of(
            conn,
            "INSERT INTO matches (group_id, format, points_to, win_by_two, played_at, entered_by) "
            "VALUES (:g, 'doubles', 11, true, now(), :u)",
            {"g": seed.group_a, "u": seed.alice},
        )
        assert state == INSUFFICIENT_PRIVILEGE


def test_confirmations_are_your_own(app_engine: Engine, seed: Seed) -> None:
    with as_user(app_engine, seed.carol) as conn:
        state = sqlstate_of(
            conn,
            "INSERT INTO match_confirmations (match_id, group_id, user_id, decision) "
            "VALUES (:m, :g, :u, 'dispute')",
            {"m": seed.match_a, "g": seed.group_a, "u": seed.alice},
        )
        assert state == INSUFFICIENT_PRIVILEGE
        overwritten = conn.execute(
            text("UPDATE match_confirmations SET decision = 'dispute' WHERE match_id = :m"),
            {"m": seed.match_a},
        )
        assert overwritten.rowcount == 0


def test_audit_log_is_append_only_even_for_the_lead(app_engine: Engine, seed: Seed) -> None:
    with as_user(app_engine, seed.alice) as conn:
        params = {"id": seed.audit_a}
        assert (
            sqlstate_of(conn, "UPDATE audit_log SET action = 'x' WHERE id = :id", params)
            == INSUFFICIENT_PRIVILEGE
        )
        assert (
            sqlstate_of(conn, "DELETE FROM audit_log WHERE id = :id", params)
            == INSUFFICIENT_PRIVILEGE
        )


class TestUserVisibility:
    def _visible(self, engine: Engine, viewer: object) -> set[object]:
        with as_user(engine, viewer) as conn:  # type: ignore[arg-type]
            return set(conn.execute(text("SELECT id FROM users")).scalars())

    def test_only_people_you_share_a_group_with(self, app_engine: Engine, seed: Seed) -> None:
        assert self._visible(app_engine, seed.bob) == {seed.bob, seed.dave}
        assert self._visible(app_engine, seed.dave) == {
            seed.alice,
            seed.bob,
            seed.carol,
            seed.dave,
        }

    def test_admins_also_see_people_waiting_for_approval(
        self, app_engine: Engine, seed: Seed
    ) -> None:
        assert seed.erin in self._visible(app_engine, seed.alice)
        assert seed.erin not in self._visible(app_engine, seed.carol)

    def test_removed_and_unaffiliated_people_see_only_themselves(
        self, app_engine: Engine, seed: Seed
    ) -> None:
        assert self._visible(app_engine, seed.frank) == {seed.frank}
        assert self._visible(app_engine, seed.nobody) == {seed.nobody}
        assert seed.frank not in self._visible(app_engine, seed.alice)

    def test_can_only_edit_yourself(self, app_engine: Engine, seed: Seed) -> None:
        with as_user(app_engine, seed.dave) as conn:
            other = conn.execute(
                text("UPDATE users SET display_name = 'Pwned' WHERE id = :u"), {"u": seed.bob}
            )
            assert other.rowcount == 0
            own = conn.execute(
                text("UPDATE users SET display_name = 'David' WHERE id = :u"), {"u": seed.dave}
            )
            assert own.rowcount == 1
            assert (
                sqlstate_of(
                    conn,
                    "UPDATE users SET auth_subject = 'x' WHERE id = :u",
                    {"u": seed.dave},
                )
                == INSUFFICIENT_PRIVILEGE
            )
