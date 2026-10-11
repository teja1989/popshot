"""Usage metrics (migration 0009): what's recorded, who can see it, and the numbers."""

import secrets
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import Connection, Engine, Row, text

from tests.db.conftest import INSUFFICIENT_PRIVILEGE, People, as_user, create, sqlstate_of

pytestmark = pytest.mark.db


def activity_days(owner_engine: Engine, user_id: object) -> list[date]:
    with owner_engine.connect() as conn:
        return list(
            conn.execute(
                text("SELECT day FROM user_activity WHERE user_id = :u ORDER BY day"),
                {"u": user_id},
            ).scalars()
        )


def test_a_signed_in_request_records_today_once(people: People, owner_engine: Engine) -> None:
    casey = people.new("Casey")
    me = people.user_id(casey)
    people.client.get("/v1/groups", headers=casey)
    people.client.get("/v1/me", headers=casey)
    with owner_engine.connect() as conn:
        today = conn.execute(text("SELECT current_date")).scalar_one()
    assert activity_days(owner_engine, me) == [today]


def test_the_app_can_only_add_today_for_itself(people: People, app_engine: Engine) -> None:
    casey = people.user_id(people.new("Casey"))
    sam = people.user_id(people.new("Sam"))
    insert = "INSERT INTO user_activity (user_id, day) VALUES (:u, {day})"
    today = insert.format(day="current_date")
    with as_user(app_engine, casey) as conn:
        # The metric functions belong to the admin service (test_admin_api.py).
        assert sqlstate_of(conn, "SELECT count(*) FROM user_activity") == INSUFFICIENT_PRIVILEGE
        # Not for someone else, not for another day.
        assert (
            sqlstate_of(conn, insert.format(day="current_date"), {"u": sam})
            == INSUFFICIENT_PRIVILEGE
        )
        assert (
            sqlstate_of(conn, insert.format(day="current_date - 1"), {"u": casey})
            == INSUFFICIENT_PRIVILEGE
        )
        # Today, for yourself: fine (already there from the sign-in request, as the API does it).
        assert sqlstate_of(conn, today + " ON CONFLICT DO NOTHING", {"u": casey}) is None


@pytest.fixture
def owner_tx(owner_engine: Engine) -> Iterator[Connection]:
    """An owner transaction that may insert backdated activity; all rolled back after."""
    with owner_engine.connect() as conn:
        tx = conn.begin()
        conn.execute(
            text(
                "CREATE POLICY test_insert ON user_activity FOR INSERT TO CURRENT_USER "
                "WITH CHECK (true)"
            )
        )
        yield conn
        tx.rollback()


def new_user(conn: Connection, created_at: datetime) -> object:
    return conn.execute(
        text(
            "INSERT INTO users (auth_subject, display_name, created_at) "
            "VALUES (:s, 'Metric', :at) RETURNING id"
        ),
        {"s": f"metrics-{secrets.token_hex(8)}", "at": created_at},
    ).scalar_one()


def monday(weeks_ago: int) -> date:
    today = datetime.now(UTC).date()
    return today - timedelta(days=today.weekday() + 7 * weeks_ago)


def test_retention_by_signup_week(owner_tx: Connection) -> None:
    cohort = monday(5)
    signed_up = datetime.combine(cohort, datetime.min.time(), tzinfo=UTC) + timedelta(hours=12)
    users = [new_user(owner_tx, signed_up) for _ in range(4)]
    # Week 1: three of them come back; week 2: two; week 4: one.
    seen = {1: users[:3], 2: users[:2], 4: users[:1]}
    for weeks_later, who in seen.items():
        for user in who:
            owner_tx.execute(
                text("INSERT INTO user_activity (user_id, day) VALUES (:u, :d)"),
                {"u": user, "d": cohort + timedelta(days=7 * weeks_later + 2)},
            )
    rows = {
        r.cohort_week: r for r in owner_tx.execute(text("SELECT * FROM app_metrics_retention(8)"))
    }
    row = rows[cohort]
    assert (row.signed_up, row.week_1, row.week_2, row.week_3, row.week_4) == (4, 3, 2, 0, 1)


def test_weekly_numbers_count_backdated_activity(owner_tx: Connection) -> None:
    week = monday(3)
    for i in range(3):
        user = new_user(owner_tx, datetime.now(UTC) - timedelta(days=60))
        owner_tx.execute(
            text("INSERT INTO user_activity (user_id, day) VALUES (:u, :d)"),
            {"u": user, "d": week + timedelta(days=i)},
        )
    rows = {r.week_start: r for r in owner_tx.execute(text("SELECT * FROM app_metrics_weekly(6)"))}
    assert len(rows) == 6
    assert rows[week].active_users >= 3


def test_a_game_makes_a_crew_active_this_week(people: People, owner_engine: Engine) -> None:
    # No owner_tx here: its lock on user_activity would block the API's requests.
    def this_week() -> Row[Any]:
        with owner_engine.connect() as conn:
            return conn.execute(text("SELECT * FROM app_metrics_weekly(1)")).one()

    before = this_week()
    casey = people.new("Casey")
    gid = create(people, casey)["id"]
    me = people.client.get(f"/v1/groups/{gid}/players", headers=casey).json()[0]["id"]
    guest = people.client.post(
        f"/v1/groups/{gid}/players", json={"display_name": "Gary"}, headers=casey
    ).json()["id"]
    logged = people.client.post(
        f"/v1/groups/{gid}/matches",
        json={
            "format": "singles",
            "points_to": 11,
            "win_by_two": True,
            "best_of": 1,
            "team_a": [me],
            "team_b": [guest],
            "games": [{"team_a": 11, "team_b": 5}],
        },
        headers=casey,
    )
    assert logged.status_code == 201, logged.text
    now = this_week()
    assert now.games == before.games + 1
    assert now.active_crews >= before.active_crews + 1
    assert now.new_users >= before.new_users + 1
    assert now.active_users >= before.active_users + 1


def test_old_activity_is_purged(owner_tx: Connection) -> None:
    user = new_user(owner_tx, datetime.now(UTC) - timedelta(days=500))
    for days_ago in (420, 30):
        owner_tx.execute(
            text("INSERT INTO user_activity (user_id, day) VALUES (:u, current_date - :n)"),
            {"u": user, "n": days_ago},
        )
    assert owner_tx.execute(text("SELECT app_jobs_purge_activity()")).scalar_one() >= 1
    left = owner_tx.execute(
        text("SELECT current_date - day FROM user_activity WHERE user_id = :u"), {"u": user}
    ).scalars()
    assert list(left) == [30]
