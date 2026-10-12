"""Cross-group isolation (ADR 0002).

Bob leads group B. For every protected table he must not be able to read, insert, update or
delete group A's rows, even by exact ID, nor attach A's rows to B's. Bob is an admin in B,
so any policy that checked the role but forgot the group would fail here.

A new table must be added to TABLES; test_every_table_is_covered enforces that.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import Engine, text

from tests.db.conftest import (
    FOREIGN_KEY_VIOLATION,
    INSUFFICIENT_PRIVILEGE,
    INVALID_TEXT,
    Seed,
    as_user,
    new_token_hash,
    sqlstate_of,
)

pytestmark = pytest.mark.db

Params = Callable[[Seed], dict[str, Any]]


@dataclass(frozen=True)
class TableSpec:
    name: str
    # WHERE clause matching one of group A's rows, and its parameters.
    a_row: str
    a_params: Params
    # Same shape, for one of group B's rows (Bob's own).
    b_params: Params
    # SET clause for a no-op update, or None if popshot_app has no UPDATE on the table.
    noop_update: str | None
    # Whether popshot_app may DELETE at all.
    deletable: bool
    # INSERT of a row into group A, attempted by Bob.
    insert_into_a: tuple[str, Params]
    # INSERTs of a group B row that references group A's rows (must fail the FK).
    cross_refs: list[tuple[str, Params]]
    group_column: str = "group_id"


TABLES: list[TableSpec] = [
    TableSpec(
        name="groups",
        a_row="id = :id",
        a_params=lambda s: {"id": s.group_a},
        b_params=lambda s: {"id": s.group_b},
        noop_update="name = name",
        deletable=True,
        insert_into_a=(
            "INSERT INTO groups (id, name, created_by) VALUES (:g, 'Hijack', :u)",
            lambda s: {"g": s.group_a, "u": s.bob},
        ),
        cross_refs=[],
        group_column="id",
    ),
    TableSpec(
        name="group_members",
        a_row="group_id = :g AND user_id = :u",
        a_params=lambda s: {"g": s.group_a, "u": s.carol},
        b_params=lambda s: {"g": s.group_b, "u": s.dave},
        noop_update="status = status",
        deletable=False,
        insert_into_a=(
            "INSERT INTO group_members (group_id, user_id, role, status) "
            "VALUES (:g, :u, 'lead', 'active')",
            lambda s: {"g": s.group_a, "u": s.bob},
        ),
        cross_refs=[],
    ),
    TableSpec(
        name="group_invites",
        a_row="id = :id",
        a_params=lambda s: {"id": s.invite_a},
        b_params=lambda s: {"id": s.invite_b},
        noop_update="revoked_at = revoked_at",
        deletable=True,
        insert_into_a=(
            "INSERT INTO group_invites (group_id, token_hash, created_by, expires_at) "
            "VALUES (:g, :h, :u, now() + interval '1 day')",
            lambda s: {"g": s.group_a, "h": new_token_hash(), "u": s.bob},
        ),
        cross_refs=[],
    ),
    TableSpec(
        name="players",
        a_row="id = :id",
        a_params=lambda s: {"id": s.player_guest_a},
        b_params=lambda s: {"id": s.player_bob_b},
        noop_update="display_name = display_name",
        deletable=False,
        insert_into_a=(
            "INSERT INTO players (group_id, display_name) VALUES (:g, 'Mallory')",
            lambda s: {"g": s.group_a},
        ),
        cross_refs=[
            # A user who isn't a member of B can't be made a player in B.
            (
                "INSERT INTO players (group_id, user_id, display_name) VALUES (:g, :u, 'Alice?')",
                lambda s: {"g": s.group_b, "u": s.alice},
            ),
        ],
    ),
    TableSpec(
        name="matches",
        a_row="id = :id",
        a_params=lambda s: {"id": s.match_a},
        b_params=lambda s: {"id": s.match_b},
        noop_update="status = status",
        deletable=True,
        insert_into_a=(
            "INSERT INTO matches (group_id, format, points_to, win_by_two, played_at, "
            "entered_by) VALUES (:g, 'doubles', 11, true, now(), :u)",
            lambda s: {"g": s.group_a, "u": s.bob},
        ),
        cross_refs=[],
    ),
    TableSpec(
        name="match_players",
        a_row="match_id = :m AND player_id = :p",
        a_params=lambda s: {"m": s.match_a, "p": s.player_guest_a},
        b_params=lambda s: {"m": s.match_b, "p": s.player_bob_b},
        noop_update="team = team",
        deletable=True,
        insert_into_a=(
            "INSERT INTO match_players (match_id, group_id, player_id, team) "
            "VALUES (:m, :g, :p, 'A')",
            lambda s: {"m": s.match_a, "g": s.group_a, "p": s.player_guest_a},
        ),
        cross_refs=[
            (
                "INSERT INTO match_players (match_id, group_id, player_id, team) "
                "VALUES (:m, :g, :p, 'A')",
                lambda s: {"m": s.match_b, "g": s.group_b, "p": s.player_guest_a},
            ),
            (
                "INSERT INTO match_players (match_id, group_id, player_id, team) "
                "VALUES (:m, :g, :p, 'A')",
                lambda s: {"m": s.match_a, "g": s.group_b, "p": s.player_bob_b},
            ),
        ],
    ),
    TableSpec(
        name="match_games",
        a_row="match_id = :m AND game_number = 1",
        a_params=lambda s: {"m": s.match_a},
        b_params=lambda s: {"m": s.match_b},
        noop_update="team_a_score = team_a_score",
        deletable=True,
        insert_into_a=(
            "INSERT INTO match_games (match_id, group_id, game_number, team_a_score, "
            "team_b_score) VALUES (:m, :g, 2, 11, 3)",
            lambda s: {"m": s.match_a, "g": s.group_a},
        ),
        cross_refs=[
            (
                "INSERT INTO match_games (match_id, group_id, game_number, team_a_score, "
                "team_b_score) VALUES (:m, :g, 2, 11, 3)",
                lambda s: {"m": s.match_a, "g": s.group_b},
            ),
        ],
    ),
    TableSpec(
        name="match_confirmations",
        a_row="match_id = :m",
        a_params=lambda s: {"m": s.match_a},
        b_params=lambda s: {"m": s.match_b},
        noop_update="decision = decision",
        deletable=False,
        insert_into_a=(
            "INSERT INTO match_confirmations (match_id, group_id, user_id, decision) "
            "VALUES (:m, :g, :u, 'dispute')",
            lambda s: {"m": s.match_a, "g": s.group_a, "u": s.bob},
        ),
        cross_refs=[
            (
                "INSERT INTO match_confirmations (match_id, group_id, user_id, decision) "
                "VALUES (:m, :g, :u, 'dispute')",
                lambda s: {"m": s.match_a, "g": s.group_b, "u": s.bob},
            ),
        ],
    ),
    TableSpec(
        name="match_reflections",
        a_row="match_id = :m AND user_id = :u",
        a_params=lambda s: {"m": s.match_a, "u": s.alice},
        b_params=lambda s: {"m": s.match_b, "u": s.bob},
        noop_update="went_well = went_well",
        deletable=False,
        insert_into_a=(
            "INSERT INTO match_reflections (match_id, group_id, user_id) VALUES (:m, :g, :u)",
            lambda s: {"m": s.match_a, "g": s.group_a, "u": s.bob},
        ),
        cross_refs=[
            (
                "INSERT INTO match_reflections (match_id, group_id, user_id) VALUES (:m, :g, :u)",
                lambda s: {"m": s.match_a, "g": s.group_b, "u": s.bob},
            ),
        ],
    ),
    TableSpec(
        name="ratings",
        a_row="group_id = :g AND player_id = :p",
        a_params=lambda s: {"g": s.group_a, "p": s.player_alice_a},
        b_params=lambda s: {"g": s.group_b, "p": s.player_bob_b},
        noop_update="rating = rating",
        deletable=True,
        insert_into_a=(
            "INSERT INTO ratings (group_id, player_id, rating) VALUES (:g, :p, 1500)",
            lambda s: {"g": s.group_a, "p": s.player_guest_a},
        ),
        cross_refs=[
            (
                "INSERT INTO ratings (group_id, player_id, rating) VALUES (:g, :p, 1500)",
                lambda s: {"g": s.group_b, "p": s.player_guest_a},
            ),
        ],
    ),
    TableSpec(
        name="rating_history",
        a_row="id = :id",
        a_params=lambda s: {"id": s.rating_history_a},
        b_params=lambda s: {"id": s.rating_history_b},
        noop_update=None,
        deletable=False,
        insert_into_a=(
            "INSERT INTO rating_history (group_id, player_id, match_id, rating_before, "
            "rating_after) VALUES (:g, :p, :m, 1, 2)",
            lambda s: {"g": s.group_a, "p": s.player_guest_a, "m": s.match_a},
        ),
        cross_refs=[
            (
                "INSERT INTO rating_history (group_id, player_id, match_id, rating_before, "
                "rating_after) VALUES (:g, :p, :m, 1, 2)",
                lambda s: {"g": s.group_b, "p": s.player_bob_b, "m": s.match_a},
            ),
        ],
    ),
    TableSpec(
        name="audit_log",
        a_row="id = :id",
        a_params=lambda s: {"id": s.audit_a},
        b_params=lambda s: {"id": s.audit_b},
        noop_update=None,
        deletable=False,
        insert_into_a=(
            "INSERT INTO audit_log (group_id, actor_user_id, action) "
            "VALUES (:g, :u, 'match.created')",
            lambda s: {"g": s.group_a, "u": s.bob},
        ),
        cross_refs=[],
    ),
]

TABLES += [
    TableSpec(
        name="play_nights",
        a_row="id = :id",
        a_params=lambda s: {"id": s.night_a},
        b_params=lambda s: {"id": s.night_b},
        noop_update="venue = venue",
        deletable=False,
        insert_into_a=(
            "INSERT INTO play_nights (group_id, starts_at, venue, created_by) "
            "VALUES (:g, now() + interval '1 day', 'Sneaky', :u)",
            lambda s: {"g": s.group_a, "u": s.bob},
        ),
        cross_refs=[],
    ),
    TableSpec(
        name="play_night_rsvps",
        a_row="night_id = :n AND user_id = :u",
        a_params=lambda s: {"n": s.night_a, "u": s.alice},
        b_params=lambda s: {"n": s.night_b, "u": s.bob},
        noop_update="answer = answer",
        deletable=True,
        insert_into_a=(
            "INSERT INTO play_night_rsvps (night_id, group_id, user_id, answer) "
            "VALUES (:n, :g, :u, 'out')",
            lambda s: {"n": s.night_a, "g": s.group_a, "u": s.bob},
        ),
        cross_refs=[
            # Bob's own group B, but group A's night.
            (
                "INSERT INTO play_night_rsvps (night_id, group_id, user_id, answer) "
                "VALUES (:n, :g, :u, 'out')",
                lambda s: {"n": s.night_a, "g": s.group_b, "u": s.bob},
            ),
        ],
    ),
]

TABLES += [
    TableSpec(
        name="recap_texts",
        a_row="group_id = :g AND outing_key = :k",
        a_params=lambda s: {"g": s.group_a, "k": s.match_a},
        b_params=lambda s: {"g": s.group_b, "k": s.match_b},
        noop_update="headline = headline",
        deletable=False,
        insert_into_a=(
            "INSERT INTO recap_texts (group_id, outing_key, facts_hash, status, model) "
            "VALUES (:g, gen_random_uuid(), repeat('b', 64), 'failed', 'gemini-test')",
            lambda s: {"g": s.group_a},
        ),
        cross_refs=[],
    ),
]

TABLE_IDS = [t.name for t in TABLES]


def test_every_table_is_covered(owner_engine: Engine) -> None:
    with owner_engine.connect() as conn:
        tables = set(
            conn.execute(
                text(
                    "SELECT relname FROM pg_class WHERE relkind = 'r' "
                    "AND relnamespace = 'public'::regnamespace"
                )
            ).scalars()
        )
    # These aren't group tables. test_focus_api.py covers user_focus;
    # test_notifications_api.py covers push_subscriptions and notification_settings.
    # test_metrics.py covers user_activity; test_admin_api.py covers admin_views;
    # test_admin_actions_api.py covers admin_actions.
    personal = {
        "users",
        "user_focus",
        "push_subscriptions",
        "notification_settings",
        "user_activity",
        "admin_views",
        "admin_actions",
        # No role but the owner's job functions can touch it; test_tick.py covers it.
        "recap_notifications",
    }
    assert tables - {"alembic_version", *personal} == set(TABLE_IDS)


@pytest.mark.parametrize("table", TABLES, ids=TABLE_IDS)
def test_bob_can_see_his_own_rows(app_engine: Engine, seed: Seed, table: TableSpec) -> None:
    """Sanity check: the same queries do work for the right group."""
    with as_user(app_engine, seed.bob) as conn:
        found = conn.execute(
            text(f"SELECT count(*) FROM {table.name} WHERE {table.a_row}"), table.b_params(seed)
        ).scalar_one()
    assert found == 1


@pytest.mark.parametrize("table", TABLES, ids=TABLE_IDS)
def test_cannot_select_other_groups_rows(app_engine: Engine, seed: Seed, table: TableSpec) -> None:
    with as_user(app_engine, seed.bob) as conn:
        by_id = conn.execute(
            text(f"SELECT count(*) FROM {table.name} WHERE {table.a_row}"), table.a_params(seed)
        ).scalar_one()
        by_group = conn.execute(
            text(f"SELECT count(*) FROM {table.name} WHERE {table.group_column} = :g"),
            {"g": seed.group_a},
        ).scalar_one()
        groups_seen = set(
            conn.execute(text(f"SELECT DISTINCT {table.group_column} FROM {table.name}")).scalars()
        )
    assert by_id == 0
    assert by_group == 0
    assert groups_seen == {seed.group_b}


@pytest.mark.parametrize("table", TABLES, ids=TABLE_IDS)
def test_cannot_update_other_groups_rows(app_engine: Engine, seed: Seed, table: TableSpec) -> None:
    with as_user(app_engine, seed.bob) as conn:
        if table.noop_update is None:
            sql = f"UPDATE {table.name} SET {table.group_column} = {table.group_column} "
            assert sqlstate_of(conn, sql + f"WHERE {table.a_row}", table.a_params(seed)) == (
                INSUFFICIENT_PRIVILEGE
            )
            return
        result = conn.execute(
            text(f"UPDATE {table.name} SET {table.noop_update} WHERE {table.a_row}"),
            table.a_params(seed),
        )
        assert result.rowcount == 0


@pytest.mark.parametrize("table", TABLES, ids=TABLE_IDS)
def test_cannot_delete_other_groups_rows(app_engine: Engine, seed: Seed, table: TableSpec) -> None:
    sql = f"DELETE FROM {table.name} WHERE {table.a_row}"
    with as_user(app_engine, seed.bob) as conn:
        if not table.deletable:
            assert sqlstate_of(conn, sql, table.a_params(seed)) == INSUFFICIENT_PRIVILEGE
            return
        assert conn.execute(text(sql), table.a_params(seed)).rowcount == 0
    with as_user(app_engine, seed.alice) as conn:
        still_there = conn.execute(
            text(f"SELECT count(*) FROM {table.name} WHERE {table.a_row}"), table.a_params(seed)
        ).scalar_one()
    assert still_there == 1


@pytest.mark.parametrize("table", TABLES, ids=TABLE_IDS)
def test_cannot_insert_into_other_group(app_engine: Engine, seed: Seed, table: TableSpec) -> None:
    sql, params = table.insert_into_a
    with as_user(app_engine, seed.bob) as conn:
        assert sqlstate_of(conn, sql, params(seed)) == INSUFFICIENT_PRIVILEGE


@pytest.mark.parametrize(
    ("table", "index"),
    [(t, i) for t in TABLES for i in range(len(t.cross_refs))],
    ids=[f"{t.name}-{i}" for t in TABLES for i in range(len(t.cross_refs))],
)
def test_cannot_reference_other_groups_rows(
    app_engine: Engine, seed: Seed, table: TableSpec, index: int
) -> None:
    sql, params = table.cross_refs[index]
    with as_user(app_engine, seed.bob) as conn:
        assert sqlstate_of(conn, sql, params(seed)) == FOREIGN_KEY_VIOLATION


@pytest.mark.parametrize("table", TABLES, ids=TABLE_IDS)
def test_cannot_move_own_rows_into_other_group(
    app_engine: Engine, seed: Seed, table: TableSpec
) -> None:
    """popshot_app has no UPDATE on any group_id column."""
    sql = f"UPDATE {table.name} SET {table.group_column} = :target WHERE {table.a_row}"
    with as_user(app_engine, seed.bob) as conn:
        params = {**table.b_params(seed), "target": seed.group_a}
        assert sqlstate_of(conn, sql, params) == INSUFFICIENT_PRIVILEGE


ALL_TABLES = ["users", *TABLE_IDS]


@pytest.mark.parametrize("table", ALL_TABLES)
def test_no_context_sees_nothing(app_engine: Engine, seed: Seed, table: str) -> None:
    with as_user(app_engine, None) as conn:
        assert conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one() == 0


@pytest.mark.parametrize("table", ALL_TABLES)
def test_unknown_user_sees_nothing(app_engine: Engine, seed: Seed, table: str) -> None:
    with as_user(app_engine, uuid4()) as conn:
        assert conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one() == 0


@pytest.mark.parametrize("table", TABLES, ids=TABLE_IDS)
def test_no_context_cannot_write(app_engine: Engine, seed: Seed, table: TableSpec) -> None:
    sql, params = table.insert_into_a
    with as_user(app_engine, None) as conn:
        assert sqlstate_of(conn, sql, params(seed)) == INSUFFICIENT_PRIVILEGE
        if table.noop_update is not None:
            result = conn.execute(
                text(f"UPDATE {table.name} SET {table.noop_update}"),
            )
            assert result.rowcount == 0
        if table.deletable:
            assert conn.execute(text(f"DELETE FROM {table.name}")).rowcount == 0


def test_malformed_context_fails_closed(app_engine: Engine, seed: Seed) -> None:
    with app_engine.connect() as conn, conn.begin():
        conn.execute(text("SELECT set_config('app.user_id', 'not-a-uuid', true)"))
        assert sqlstate_of(conn, "SELECT count(*) FROM matches") == INVALID_TEXT


def test_context_does_not_outlive_its_transaction(app_engine: Engine, seed: Seed) -> None:
    with app_engine.connect() as conn:
        with conn.begin():
            conn.execute(text("SELECT set_config('app.user_id', :u, true)"), {"u": str(seed.bob)})
            assert conn.execute(text("SELECT count(*) FROM matches")).scalar_one() == 1
        with conn.begin():
            assert conn.execute(text("SELECT count(*) FROM matches")).scalar_one() == 0
            assert conn.execute(
                text("SELECT current_setting('app.user_id', true)")
            ).scalar_one() in (None, "")
