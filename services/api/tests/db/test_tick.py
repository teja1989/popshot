"""The scheduled job (popshot_api.ops.tick): reminders and purging deleted groups, run as
the real popshot_jobs role."""

import os
import secrets
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.pool import NullPool

from popshot_api.main import create_app
from popshot_api.ops.tick import run
from tests.conftest import make_settings
from tests.db.conftest import People, as_user, committed_as, create
from tests.db.test_games_api import join_and_approve, log, players
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


@pytest.fixture(scope="session")
def jobs_engine(owner_engine: Engine) -> Iterator[Engine]:
    """A login user in popshot_jobs, like the job's IAM user on Cloud SQL. Made by the
    bootstrap admin, which created popshot_jobs and so may grant it."""
    admin = os.environ.get("POPSHOT_BOOTSTRAP_ADMIN_URL")
    if not admin:
        pytest.skip("POPSHOT_BOOTSTRAP_ADMIN_URL not set")
    password = secrets.token_hex(16)
    with psycopg.connect(admin, autocommit=True) as conn:
        exists = conn.execute("SELECT 1 FROM pg_roles WHERE rolname = 'popshot_jobs_test'")
        verb = sql.SQL("ALTER") if exists.fetchone() else sql.SQL("CREATE")
        conn.execute(
            sql.SQL("{} ROLE popshot_jobs_test LOGIN PASSWORD {}").format(
                verb, sql.Literal(password)
            )
        )
        conn.execute("GRANT popshot_jobs TO popshot_jobs_test")
    url = make_url(str(owner_engine.url)).set(username="popshot_jobs_test", password=password)
    engine = create_engine(url, poolclass=NullPool)
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
    for table in ("play_nights", "users", "push_subscriptions", "groups", "recap_notifications"):
        with jobs_engine.connect() as conn, pytest.raises(ProgrammingError, match="denied"):
            conn.execute(text(f"SELECT 1 FROM {table} LIMIT 1"))
    riley = people.user_id(people.new("Riley"))
    for call in (
        "SELECT * FROM app_jobs_due_reminders('day')",
        "SELECT app_purge_deleted_groups()",
        "SELECT * FROM app_jobs_recent_matches(now())",
        "SELECT app_jobs_claim_recap(gen_random_uuid(), gen_random_uuid())",
        "SELECT * FROM app_jobs_recap_targets(gen_random_uuid(), '{}')",
        "SELECT * FROM recap_notifications",
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
    assert who(sender, crew) == {"Casey": "Meetup in about 20 hours", "Sam": "Are you in?"}
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
        "Casey": "Meetup in about 2 hours",
        "Sam": "Meetup in about 2 hours",
    }


def test_short_notice_gets_one_reminder(
    people: People,
    crew: dict[str, Any],
    sender: RecordingSender,
    jobs_engine: Engine,
) -> None:
    plan(people, crew["casey"], crew["group_id"], starts_at=soon(1))
    tick(jobs_engine, sender)
    assert who(sender, crew) == {"Casey": "Meetup in about 1 hour"}
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
    assert who(sender, crew) == {"Casey": "Meetup in about 12 hours", "Jo": "Are you in?"}


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
    assert who(sender, crew)["Casey"] == "Meetup in about 8 hours"
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


def singles(people: People, crew: dict[str, Any], a: str, b: str) -> str:
    ids = {name: p["id"] for name, p in players(people, crew["casey"], crew["group_id"]).items()}
    response = log(
        people,
        crew["casey"],
        crew["group_id"],
        format="singles",
        team_a=[ids[a]],
        team_b=[ids[b]],
        games=[{"team_a": 11, "team_b": 7}],
    )
    assert response.status_code == 201, response.text
    match_id: str = response.json()["id"]
    return match_id


def played_ago(app_engine: Engine, people: People, crew: dict[str, Any], hours: float) -> None:
    """Move the crew's games back by `hours`, keeping their order."""
    with committed_as(app_engine, people.user_id(crew["casey"])) as conn:
        conn.execute(
            text(
                "UPDATE matches SET played_at = played_at - make_interval(secs => :s) "
                "WHERE group_id = :g"
            ),
            {"s": hours * 3600, "g": crew["group_id"]},
        )


def recaps_sent(sender: RecordingSender, crew: dict[str, Any]) -> dict[str, Any]:
    names = {e: n for n, e in crew["devices"].items()}
    return {names[e]: m for e, m in sender.sent if e in names and m.title == "Your recap is ready"}


def test_players_hear_their_recap_is_ready_once(
    people: People,
    crew: dict[str, Any],
    sender: RecordingSender,
    jobs_engine: Engine,
    app_engine: Engine,
) -> None:
    first = singles(people, crew, "Casey", "Sam")
    singles(people, crew, "Sam", "Casey")
    # Just played: too soon.
    tick(jobs_engine, sender)
    assert recaps_sent(sender, crew) == {}

    played_ago(app_engine, people, crew, 2)
    summary = tick(jobs_engine, sender)
    sent = recaps_sent(sender, crew)
    # Casey and Sam played; Jo didn't, so isn't told.
    assert set(sent) == {"Casey", "Sam"}
    assert summary.announced_recaps == 1
    message = sent["Casey"]
    assert message.url == f"/groups/{crew['group_id']}/recaps/{first}"
    # No one's name on the lock screen.
    assert "Casey" not in message.body
    assert "Sam" not in message.body
    assert message.body.endswith("2 games. Tap to see the awards.")

    # Once only.
    tick(jobs_engine, sender)
    assert recaps_sent(sender, crew) == {}


def test_recaps_can_be_muted(
    people: People,
    crew: dict[str, Any],
    sender: RecordingSender,
    jobs_engine: Engine,
    app_engine: Engine,
) -> None:
    muted = people.client.put(
        "/v1/me/notifications", json={"muted": ["recaps"]}, headers=crew["sam"]
    )
    assert muted.status_code == 200, muted.text
    singles(people, crew, "Casey", "Sam")
    played_ago(app_engine, people, crew, 2)
    tick(jobs_engine, sender)
    assert set(recaps_sent(sender, crew)) == {"Casey"}


def test_an_outing_over_for_more_than_six_hours_is_left_alone(
    people: People,
    crew: dict[str, Any],
    sender: RecordingSender,
    jobs_engine: Engine,
    app_engine: Engine,
) -> None:
    singles(people, crew, "Jo", "Casey")
    played_ago(app_engine, people, crew, 8)
    summary = tick(jobs_engine, sender)
    assert recaps_sent(sender, crew) == {}
    assert summary.announced_recaps == 0
    # Not claimed either: it's simply past its time.
    with jobs_engine.connect() as conn:
        rows = conn.execute(
            text("SELECT * FROM app_jobs_recent_matches(now() - interval '1 day')")
        ).all()
    assert any(str(r.group_id) == crew["group_id"] for r in rows)
