"""Fixtures for tests against a real Postgres.

Needs two URLs, both for the same database:
  POPSHOT_MIGRATION_DATABASE_URL  the migrator login user (member of popshot_owner)
  POPSHOT_TEST_APP_DATABASE_URL   the API login user (member of popshot_app)
Set them up with db/local_login_users.sql and the bootstrap (see README). Without the URLs
these tests are skipped, unless
POPSHOT_REQUIRE_DB=1 (set in CI), in which case they fail.

The session starts by migrating down to base and back up, which also proves the downgrade
works. Seed data is committed once; each test runs in a transaction that is rolled back.
"""

import os
import secrets
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Connection, Engine, create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.pool import NullPool

from popshot_api.auth.verifier import VerifiedIdentity
from popshot_api.main import create_app
from tests.conftest import make_settings
from tests.fakes import FakeTokenVerifier

API_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _url(name: str) -> str:
    value = os.environ.get(name)
    if value:
        return value
    if os.environ.get("POPSHOT_REQUIRE_DB") == "1":
        pytest.fail(f"{name} is not set and POPSHOT_REQUIRE_DB=1")
    pytest.skip(f"{name} not set; skipping database tests")


@pytest.fixture(scope="session")
def owner_url() -> str:
    return _url("POPSHOT_MIGRATION_DATABASE_URL")


@pytest.fixture(scope="session")
def app_url() -> str:
    return _url("POPSHOT_TEST_APP_DATABASE_URL")


@pytest.fixture(scope="session")
def migrated(owner_url: str) -> None:
    config = Config(os.path.join(API_ROOT, "alembic.ini"))
    config.attributes["database_url"] = owner_url
    config.attributes["configure_logger"] = False
    command.downgrade(config, "base")
    command.upgrade(config, "head")


@pytest.fixture(scope="session")
def owner_engine(owner_url: str, migrated: None) -> Iterator[Engine]:
    engine = create_engine(owner_url, poolclass=NullPool)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def app_engine(app_url: str, migrated: None) -> Iterator[Engine]:
    engine = create_engine(app_url, pool_size=2)
    yield engine
    engine.dispose()


def set_user(conn: Connection, user_id: UUID | None) -> None:
    if user_id is not None:
        conn.execute(text("SELECT set_config('app.user_id', :u, true)"), {"u": str(user_id)})


@contextmanager
def as_user(engine: Engine, user_id: UUID | None) -> Iterator[Connection]:
    """A transaction acting as `user_id` (or with no context). Always rolled back."""
    with engine.connect() as conn:
        tx = conn.begin()
        try:
            set_user(conn, user_id)
            yield conn
        finally:
            tx.rollback()


@contextmanager
def committed_as(engine: Engine, user_id: UUID | None) -> Iterator[Connection]:
    with engine.begin() as conn:
        set_user(conn, user_id)
        yield conn


def sqlstate_of(conn: Connection, sql: str, params: dict[str, Any] | None = None) -> str | None:
    """Run a statement in a savepoint; return its SQLSTATE if it failed, else None."""
    savepoint = conn.begin_nested()
    try:
        conn.execute(text(sql), params or {})
    except DBAPIError as exc:
        savepoint.rollback()
        return getattr(exc.orig, "sqlstate", None)
    savepoint.rollback()
    return None


INSUFFICIENT_PRIVILEGE = "42501"  # RLS check failed or no grant
FOREIGN_KEY_VIOLATION = "23503"
INVALID_TEXT = "22P02"


@dataclass(frozen=True)
class Seed:
    alice: UUID  # lead of A
    bob: UUID  # lead of B
    carol: UUID  # member of A
    dave: UUID  # member of A and B
    erin: UUID  # pending in A
    frank: UUID  # removed from A
    nobody: UUID  # signed in, in no group
    group_a: UUID
    group_b: UUID
    invite_a: UUID
    invite_b: UUID
    player_alice_a: UUID
    player_guest_a: UUID
    player_bob_b: UUID
    player_dave_b: UUID
    match_a: UUID
    match_b: UUID
    rating_history_a: int
    rating_history_b: int
    audit_a: int
    audit_b: int


def new_token_hash() -> bytes:
    return secrets.token_bytes(32)


def _resolve(conn: Connection, subject: str) -> UUID:
    user_id: UUID = conn.execute(
        text("SELECT app_resolve_user(:s, :n, NULL)"),
        {"s": f"{subject}-{secrets.token_hex(4)}", "n": subject.title()},
    ).scalar_one()
    return user_id


def _scalar(conn: Connection, sql: str, **params: Any) -> Any:
    return conn.execute(text(sql), params).scalar_one()


def _create_invite(
    conn: Connection, group: UUID, creator: UUID, approval: bool
) -> tuple[UUID, bytes]:
    token_hash = new_token_hash()
    invite_id: UUID = _scalar(
        conn,
        """INSERT INTO group_invites (group_id, token_hash, created_by, expires_at, max_uses,
                                      requires_approval)
           VALUES (:g, :h, :u, now() + interval '1 day', 10, :a) RETURNING id""",
        g=group,
        h=token_hash,
        u=creator,
        a=approval,
    )
    return invite_id, token_hash


def _redeem(engine: Engine, user: UUID, token_hash: bytes) -> None:
    with committed_as(engine, user) as conn:
        conn.execute(text("SELECT * FROM app_redeem_invite(:h)"), {"h": token_hash})


def _add_game_data(
    conn: Connection, group: UUID, entered_by: UUID, team_a: list[UUID], team_b: list[UUID]
) -> tuple[UUID, int, int]:
    match_id: UUID = _scalar(
        conn,
        """INSERT INTO matches (group_id, format, points_to, win_by_two, best_of, played_at,
                                entered_by)
           VALUES (:g, :f, 11, true, 1, now(), :u) RETURNING id""",
        g=group,
        f="doubles" if len(team_a) == 2 else "singles",
        u=entered_by,
    )
    for team, players in (("A", team_a), ("B", team_b)):
        for player in players:
            conn.execute(
                text(
                    "INSERT INTO match_players (match_id, group_id, player_id, team) "
                    "VALUES (:m, :g, :p, :t)"
                ),
                {"m": match_id, "g": group, "p": player, "t": team},
            )
    conn.execute(
        text(
            "INSERT INTO match_games (match_id, group_id, game_number, team_a_score, "
            "team_b_score) VALUES (:m, :g, 1, 11, 7)"
        ),
        {"m": match_id, "g": group},
    )
    conn.execute(
        text("INSERT INTO ratings (group_id, player_id, rating) VALUES (:g, :p, 1000)"),
        {"g": group, "p": team_a[0]},
    )
    history: int = _scalar(
        conn,
        """INSERT INTO rating_history (group_id, player_id, match_id, rating_before,
                                       rating_after)
           VALUES (:g, :p, :m, 990, 1000) RETURNING id""",
        g=group,
        p=team_a[0],
        m=match_id,
    )
    audit: int = _scalar(
        conn,
        """INSERT INTO audit_log (group_id, actor_user_id, action, target_id)
           VALUES (:g, :u, 'match.created', :m) RETURNING id""",
        g=group,
        u=entered_by,
        m=match_id,
    )
    return match_id, history, audit


@pytest.fixture(scope="session")
def seed(app_engine: Engine) -> Seed:
    with committed_as(app_engine, None) as conn:
        users = {
            name: _resolve(conn, name)
            for name in ("alice", "bob", "carol", "dave", "erin", "frank", "nobody")
        }

    def player_for(conn: Connection, group: UUID, user: UUID) -> UUID:
        player: UUID = _scalar(
            conn, "SELECT id FROM players WHERE group_id = :g AND user_id = :u", g=group, u=user
        )
        return player

    # Group A, led by Alice.
    with committed_as(app_engine, users["alice"]) as conn:
        group_a: UUID = _scalar(
            conn,
            "SELECT app_create_group('Tuesday Crew', 'doubles', 11::smallint, true)",
        )
        invite_a, open_token = _create_invite(conn, group_a, users["alice"], approval=False)
        _, approval_token = _create_invite(conn, group_a, users["alice"], approval=True)
    for name in ("carol", "dave", "frank"):
        _redeem(app_engine, users[name], open_token)
    _redeem(app_engine, users["erin"], approval_token)

    with committed_as(app_engine, users["alice"]) as conn:
        conn.execute(
            text(
                "UPDATE group_members SET status = 'removed' WHERE group_id = :g AND user_id = :u"
            ),
            {"g": group_a, "u": users["frank"]},
        )
        player_alice_a = player_for(conn, group_a, users["alice"])
        player_guest_a: UUID = _scalar(
            conn,
            "INSERT INTO players (group_id, display_name) VALUES (:g, 'Guest Gary') RETURNING id",
            g=group_a,
        )
        player_carol_a: UUID = _scalar(
            conn,
            "INSERT INTO players (group_id, user_id, display_name) "
            "VALUES (:g, :u, 'Carol') RETURNING id",
            g=group_a,
            u=users["carol"],
        )
        player_dave_a: UUID = _scalar(
            conn,
            "INSERT INTO players (group_id, user_id, display_name) "
            "VALUES (:g, :u, 'Dave') RETURNING id",
            g=group_a,
            u=users["dave"],
        )
        match_a, history_a, audit_a = _add_game_data(
            conn,
            group_a,
            users["alice"],
            [player_alice_a, player_carol_a],
            [player_dave_a, player_guest_a],
        )
    with committed_as(app_engine, users["dave"]) as conn:
        conn.execute(
            text(
                "INSERT INTO match_confirmations (match_id, group_id, user_id, decision) "
                "VALUES (:m, :g, :u, 'confirm')"
            ),
            {"m": match_a, "g": group_a, "u": users["dave"]},
        )

    # Group B, led by Bob. Dave plays in both.
    with committed_as(app_engine, users["bob"]) as conn:
        group_b: UUID = _scalar(
            conn, "SELECT app_create_group('Weekend Smash', 'singles', 15::smallint, false)"
        )
        invite_b, token_b = _create_invite(conn, group_b, users["bob"], approval=False)
    _redeem(app_engine, users["dave"], token_b)
    with committed_as(app_engine, users["bob"]) as conn:
        player_bob_b = player_for(conn, group_b, users["bob"])
        player_dave_b: UUID = _scalar(
            conn,
            "INSERT INTO players (group_id, user_id, display_name) "
            "VALUES (:g, :u, 'Dave') RETURNING id",
            g=group_b,
            u=users["dave"],
        )
        match_b, history_b, audit_b = _add_game_data(
            conn, group_b, users["bob"], [player_bob_b], [player_dave_b]
        )
    with committed_as(app_engine, users["dave"]) as conn:
        conn.execute(
            text(
                "INSERT INTO match_confirmations (match_id, group_id, user_id, decision) "
                "VALUES (:m, :g, :u, 'confirm')"
            ),
            {"m": match_b, "g": group_b, "u": users["dave"]},
        )

    return Seed(
        **users,
        group_a=group_a,
        group_b=group_b,
        invite_a=invite_a,
        invite_b=invite_b,
        player_alice_a=player_alice_a,
        player_guest_a=player_guest_a,
        player_bob_b=player_bob_b,
        player_dave_b=player_dave_b,
        match_a=match_a,
        match_b=match_b,
        rating_history_a=history_a,
        rating_history_b=history_b,
        audit_a=audit_a,
        audit_b=audit_b,
    )


class People:
    """Signs people in with fresh identities, so tests never share users or groups."""

    def __init__(self, client: TestClient, verifier: FakeTokenVerifier) -> None:
        self.client = client
        self.verifier = verifier

    def new(self, name: str) -> dict[str, str]:
        token = f"token-{secrets.token_hex(8)}"
        self.verifier.identities[token] = VerifiedIdentity(
            subject=f"groups-test-{secrets.token_hex(8)}",
            email=f"{name.lower()}@example.com",
            display_name=name,
            picture_url=None,
        )
        return {"Authorization": f"Bearer {token}"}

    def user_id(self, headers: dict[str, str]) -> UUID:
        return UUID(self.client.get("/v1/me", headers=headers).json()["id"])


@pytest.fixture
def people(app_engine: Engine) -> Iterator[People]:
    verifier = FakeTokenVerifier()
    app = create_app(make_settings(), verifier, app_engine)
    with TestClient(app) as client:
        yield People(client, verifier)


def create(
    people: People, headers: dict[str, str], name: str = "Tuesday Dinkers"
) -> dict[str, Any]:
    response = people.client.post("/v1/groups", json={"name": name}, headers=headers)
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body
