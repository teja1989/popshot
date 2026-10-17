"""Migration 0041: shared links, stored words and sent pushes move to day keys, and back."""

import os
import secrets
from collections.abc import Iterator
from datetime import date
from typing import Any
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, text

from popshot_api.recap import day_key
from tests.db.conftest import API_ROOT, People, committed_as
from tests.db.test_board_api import crew, singles  # noqa: F401  (crew is a fixture)

pytestmark = pytest.mark.db

# In New York (the crew's zone): two games one morning, one that evening, one the next day.
PLAYED = {
    "morning": "2026-09-01 09:00-04",
    "morning2": "2026-09-01 09:20-04",
    "evening": "2026-09-01 22:30-04",  # already 2 September in UTC
    "next_day": "2026-09-02 10:00-04",
}
FIRST_DAY, NEXT_DAY = date(2026, 9, 1), date(2026, 9, 2)


@pytest.fixture
def alembic(owner_url: str) -> Iterator[Config]:
    config = Config(os.path.join(API_ROOT, "alembic.ini"))
    config.attributes["database_url"] = owner_url
    config.attributes["configure_logger"] = False
    yield config
    command.upgrade(config, "head")


def keys_in(owner_engine: Engine, table: str, group_id: str) -> list[UUID]:
    with owner_engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE popshot_owner"))
        return sorted(
            conn.execute(
                text(f"SELECT outing_key FROM {table} WHERE group_id = :g"),
                {"g": group_id},
            ).scalars(),
            key=str,
        )


def test_old_outing_keys_move_to_their_day_and_back(
    people: People,
    crew: dict[str, Any],  # noqa: F811
    app_engine: Engine,
    owner_engine: Engine,
    alembic: Config,
) -> None:
    gid = crew["group_id"]
    casey, sam = people.user_id(crew["casey"]), people.user_id(crew["sam"])
    games = {name: singles(people, crew, "Casey", "Gary", (11, 3)) for name in PLAYED}
    with committed_as(app_engine, casey) as conn:
        for name, at in PLAYED.items():
            conn.execute(
                text("UPDATE matches SET played_at = :at WHERE id = :id"),
                {"at": at, "id": games[name]},
            )

    command.downgrade(alembic, "0040")
    # Keys as they were: each outing's first game. Morning and evening were two outings.
    old = [games["morning"], games["evening"], games["next_day"]]
    gone = str(uuid4())  # a key whose game was deleted
    with committed_as(app_engine, sam) as conn:
        for key in [*old, gone]:
            conn.execute(
                text(
                    "INSERT INTO recap_shares (token_hash, group_id, outing_key, created_by) "
                    "VALUES (:h, :g, :k, :u)"
                ),
                {"h": secrets.token_bytes(32), "g": gid, "k": key, "u": sam},
            )
        for key in old:
            conn.execute(
                text(
                    "INSERT INTO recap_texts (group_id, outing_key, facts_hash, status, model) "
                    "VALUES (:g, :k, repeat('c', 64), 'failed', 'gemini-test')"
                ),
                {"g": gid, "k": key},
            )
    with owner_engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE popshot_owner"))
        for key in old:
            conn.execute(
                text("INSERT INTO recap_notifications (group_id, outing_key) VALUES (:g, :k)"),
                {"g": gid, "k": key},
            )

    command.upgrade(alembic, "head")
    first, second = day_key(UUID(gid), FIRST_DAY), day_key(UUID(gid), NEXT_DAY)
    days = sorted([first, second], key=str)
    # Both of the first day's links lead to its recap; the gone key is left alone.
    assert keys_in(owner_engine, "recap_shares", gid) == sorted(
        [first, first, second, UUID(gone)], key=str
    )
    # One push record and one set of words per day.
    assert keys_in(owner_engine, "recap_notifications", gid) == days
    assert keys_in(owner_engine, "recap_texts", gid) == days

    # Back down: each day's key becomes its first game again.
    command.downgrade(alembic, "0040")
    morning, next_day = UUID(games["morning"]), UUID(games["next_day"])
    assert keys_in(owner_engine, "recap_shares", gid) == sorted(
        [morning, morning, next_day, UUID(gone)], key=str
    )
    assert keys_in(owner_engine, "recap_texts", gid) == sorted([morning, next_day], key=str)
