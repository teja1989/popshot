"""The scheduled job (popshot_api.ops.tick): reminders and purging deleted groups, run as
the real popshot_jobs role."""

import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.pool import NullPool

from popshot_api.main import create_app
from popshot_api.ops.tick import run
from tests.conftest import make_settings
from tests.db.conftest import People, as_user, committed_as, create
from tests.db.test_games_api import join_and_approve
from tests.db.test_nights_api import plan, rsvp
from tests.db.test_notifications_api import RecordingSender, device
from tests.fakes import FakeTokenVerifier

pytestmark = pytest.mark.db


@pytest.fixture
def sender() -> RecordingSender:
    return RecordingSender()


@pytest.fixture
def people(app_engine: Engine, sender: RecordingSender) -> Iterator[People]:
    app = create_app(make_settings(), FakeTokenVerifier(), app_engine, push_sender=sender)
    with TestClient(app) as client:
        yield People(client, app.state.token_verifier)


@pytest.fixture
def jobs_engine(owner_engine: Engine) -> Iterator[Engine]:
    """Connections as popshot_jobs (via the admin login, which may SET ROLE to it)."""
    admin = os.environ.get("POPSHOT_BOOTSTRAP_ADMIN_URL")
    if not admin:
        pytest.skip("POPSHOT_BOOTSTRAP_ADMIN_URL not set")
    url = make_url(admin.replace("postgresql://", "postgresql+psycopg://", 1)).set(
        database=owner_engine.url.database
    )
    engine = create_engine(url, poolclass=NullPool)

    @event.listens_for(engine, "connect")
    def _as_jobs(dbapi_conn: Any, _: Any) -> None:
        with dbapi_conn.cursor() as cur:
            cur.execute("SET ROLE popshot_jobs")
        # Committed, or the pool's rollback would undo it and leave us as the admin.
        dbapi_conn.commit()

    yield engine
    engine.dispose()


@pytest.fixture
def crew(people: People) -> dict[str, Any]:
    casey = people.new("Casey")
    group_id = create(people, casey)["id"]
    sam = join_and_approve(people, casey, group_id, "Sam")
    jo = join_and_approve(people, casey, group_id, "Jo")
    devices = {name: device(people, h) for name, h in (("Casey", casey), ("Sam", sam), ("Jo", jo))}
    return {"group_id": group_id, "casey": casey, "sam": sam, "jo": jo, "devices": devices}


def soon(hours: float) -> str:
    return (datetime.now(UTC) + timedelta(hours=hours)).isoformat()


def who(sender: RecordingSender, crew: dict[str, Any]) -> dict[str, str]:
    names = {e: n for n, e in crew["devices"].items()}
    return {names[e]: m.title for e, m in sender.sent if e in names}


def tick(jobs_engine: Engine, sender: RecordingSender) -> Any:
    sender.sent.clear()
    return run(jobs_engine, sender)


def test_the_jobs_role_can_only_run_its_functions(
    jobs_engine: Engine, app_engine: Engine, people: People
) -> None:
    for table in ("play_nights", "users", "push_subscriptions", "groups"):
        with jobs_engine.connect() as conn, pytest.raises(ProgrammingError, match="denied"):
            conn.execute(text(f"SELECT 1 FROM {table} LIMIT 1"))
    riley = people.user_id(people.new("Riley"))
    for call in (
        "SELECT * FROM app_jobs_due_reminders('day')",
        "SELECT app_purge_deleted_groups()",
    ):
        with as_user(app_engine, riley) as conn, pytest.raises(ProgrammingError, match="denied"):
            conn.execute(text(call))


def test_day_before_and_two_hours_before(
    people: People,
    crew: dict[str, Any],
    sender: RecordingSender,
    jobs_engine: Engine,
    app_engine: Engine,
) -> None:
    [night] = plan(people, crew["casey"], crew["group_id"], starts_at=soon(20)).json()
    rsvp(people, crew["jo"], night, "out")
    # Not due yet for a night 3 days away.
    plan(people, crew["casey"], crew["group_id"], starts_at=soon(72))

    tick(jobs_engine, sender)
    assert who(sender, crew) == {"Casey": "Play night in about 20 hours", "Sam": "Are you in?"}
    urls = {m.url for e, m in sender.sent if e in crew["devices"].values()}
    assert urls == {f"/groups/{crew['group_id']}/nights/{night['id']}"}
    # Not twice. (Other tests' nights can be due too, so only this crew's devices count.)
    tick(jobs_engine, sender)
    assert who(sender, crew) == {}

    # Two hours before: only the people going.
    rsvp(people, crew["sam"], night, "in")
    with committed_as(app_engine, people.user_id(crew["casey"])) as conn:
        conn.execute(
            text("UPDATE play_nights SET starts_at = now() + interval '100 minutes' WHERE id = :n"),
            {"n": night["id"]},
        )
    tick(jobs_engine, sender)
    assert who(sender, crew) == {
        "Casey": "Play night in about 2 hours",
        "Sam": "Play night in about 2 hours",
    }


def test_short_notice_gets_one_reminder(
    people: People,
    crew: dict[str, Any],
    sender: RecordingSender,
    jobs_engine: Engine,
) -> None:
    plan(people, crew["casey"], crew["group_id"], starts_at=soon(1))
    tick(jobs_engine, sender)
    assert who(sender, crew) == {"Casey": "Play night in about 1 hour"}
    tick(jobs_engine, sender)
    assert who(sender, crew) == {}


def test_no_reminders_for_cancelled_or_muted(
    people: People,
    crew: dict[str, Any],
    sender: RecordingSender,
    jobs_engine: Engine,
) -> None:
    [night] = plan(people, crew["casey"], crew["group_id"], starts_at=soon(10)).json()
    people.client.post(
        f"/v1/groups/{crew['group_id']}/nights/{night['id']}/cancel", headers=crew["casey"]
    )
    plan(people, crew["casey"], crew["group_id"], starts_at=soon(12))
    people.client.put("/v1/me/notifications", json={"muted": ["play_nights"]}, headers=crew["sam"])
    tick(jobs_engine, sender)
    # Sam muted play nights; Jo hasn't answered, so is asked.
    assert who(sender, crew) == {"Casey": "Play night in about 12 hours", "Jo": "Are you in?"}


def test_a_new_time_means_new_reminders(
    people: People,
    crew: dict[str, Any],
    sender: RecordingSender,
    jobs_engine: Engine,
) -> None:
    [night] = plan(people, crew["casey"], crew["group_id"], starts_at=soon(10)).json()
    tick(jobs_engine, sender)
    changed = people.client.patch(
        f"/v1/groups/{crew['group_id']}/nights/{night['id']}",
        json={"starts_at": soon(8), "venue": night["venue"]},
        headers=crew["casey"],
    )
    assert changed.status_code == 200
    tick(jobs_engine, sender)
    assert who(sender, crew)["Casey"] == "Play night in about 8 hours"
    # Same time, other details: no new reminder.
    people.client.patch(
        f"/v1/groups/{crew['group_id']}/nights/{night['id']}",
        json={"starts_at": changed.json()["starts_at"], "venue": "Elsewhere"},
        headers=crew["casey"],
    )
    tick(jobs_engine, sender)
    assert who(sender, crew) == {}


def test_purges_groups_past_their_restore_window(
    people: People,
    sender: RecordingSender,
    jobs_engine: Engine,
    owner_engine: Engine,
) -> None:
    lead = people.new("Casey")
    old = create(people, lead, "Old Crew")["id"]
    recent = create(people, lead, "Recent Crew")["id"]
    for gid in (old, recent):
        people.client.delete(f"/v1/groups/{gid}", headers=lead)
    with owner_engine.begin() as conn:
        conn.execute(
            text("UPDATE groups SET deleted_at = now() - interval '31 days' WHERE id = :g"),
            {"g": old},
        )
    assert tick(jobs_engine, sender).purged_groups >= 1
    with owner_engine.begin() as conn:
        left = {
            str(g)
            for g in conn.execute(
                text("SELECT id FROM groups WHERE id IN (:a, :b)"), {"a": old, "b": recent}
            ).scalars()
        }
    assert left == {recent}


def test_gone_devices_are_forgotten(
    people: People,
    crew: dict[str, Any],
    sender: RecordingSender,
    jobs_engine: Engine,
) -> None:
    plan(people, crew["casey"], crew["group_id"], starts_at=soon(5))
    sender.gone.add(crew["devices"]["Casey"])
    tick(jobs_engine, sender)
    settings = people.client.get("/v1/me/notifications", headers=crew["casey"]).json()
    assert settings["devices"] == 0
