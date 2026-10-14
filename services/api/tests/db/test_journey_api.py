"""Your journey (migration 0032, routes/journey.py): story versions, learning notes, settings,
and per-person switches, against the real database."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import Connection, Engine, text

from tests.db.conftest import INSUFFICIENT_PRIVILEGE, People, as_user, create, sqlstate_of
from tests.db.test_features import Switches, owner, switches  # noqa: F401  (a fixture)
from tests.db.test_games_api import join_and_approve

pytestmark = pytest.mark.db

Headers = dict[str, str]
STORY = {
    "origin": "A friend dragged me to a court last spring.",
    "strengths": "My serve is steady.",
    "gaps": "Dinks go into the net when I rush.",
    "goal": "Win more kitchen battles.",
}


@contextmanager
def owner_with(owner_engine: Engine, table: str, command: str) -> Iterator[Connection]:
    """As the owner, which may only read and delete these rows (for the clean-up trigger),
    with one more command allowed for this transaction only."""
    with owner(owner_engine) as conn:
        conn.execute(
            text(
                f"CREATE POLICY test_only ON {table} FOR {command} TO CURRENT_USER "
                "USING (true) WITH CHECK (true)"
            )
        )
        yield conn
        conn.execute(text(f"DROP POLICY test_only ON {table}"))


def set_rollout(owner_engine: Engine, key: str, rollout: str) -> None:
    with owner(owner_engine) as conn:
        conn.execute(
            text("UPDATE features SET rollout = :r WHERE key = :k"), {"r": rollout, "k": key}
        )


@pytest.fixture
def journey_on(owner_engine: Engine) -> Iterator[None]:
    set_rollout(owner_engine, "you.journey", "everyone")
    yield
    set_rollout(owner_engine, "you.journey", "crews")


def journey(people: People, who: Headers) -> dict[str, Any]:
    response = people.client.get("/v1/me/journey", headers=who)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def save(people: People, who: Headers, **story: Any) -> Any:
    return people.client.put("/v1/me/journey/story", json=story, headers=who)


def test_off_until_switched_on(people: People, owner_engine: Engine) -> None:
    casey = people.new("Casey")
    # It starts on the beta list with no crews, so nobody has it.
    assert people.client.get("/v1/me/journey", headers=casey).status_code == 404
    assert save(people, casey, **STORY).status_code == 404
    assert people.client.get("/v1/me/features", headers=casey).json()["you"] == []
    set_rollout(owner_engine, "you.journey", "everyone")
    try:
        assert people.client.get("/v1/me/journey", headers=casey).status_code == 200
        assert "you.journey" in people.client.get("/v1/me/features", headers=casey).json()["you"]
        set_rollout(owner_engine, "you.journey", "off")
        assert people.client.get("/v1/me/journey", headers=casey).status_code == 404
    finally:
        set_rollout(owner_engine, "you.journey", "crews")
    assert people.client.get("/v1/me/journey").status_code == 401


def test_a_beta_crew_turns_it_on_for_its_active_members(
    people: People,
    switches: Switches,  # noqa: F811
    app_engine: Engine,
) -> None:
    casey = people.new("Casey")
    group_id = create(people, casey)["id"]
    sam = join_and_approve(people, casey, group_id, "Sam")
    robin = people.new("Robin")
    switches.list_crew("you.journey", group_id)
    try:
        assert people.client.get("/v1/me/journey", headers=sam).status_code == 200
        assert people.client.get("/v1/me/journey", headers=robin).status_code == 404
        # Only 'you' switches are asked about per person; a crew switch is never on here.
        with as_user(app_engine, people.user_id(casey)) as conn:
            assert (
                conn.execute(text("SELECT app_feature_on_for_me('recaps.ai')")).scalar_one()
                is False
            )
            assert conn.execute(text("SELECT app_feature_on_for_me('you.journey')")).scalar_one()
        # Leaving the crew turns it off.
        people.client.post(f"/v1/groups/{group_id}/leave", headers=sam)
        assert people.client.get("/v1/me/journey", headers=sam).status_code == 404
    finally:
        with owner(switches.owner_engine) as conn:
            conn.execute(
                text(
                    "DELETE FROM feature_crews WHERE feature_key = 'you.journey' AND group_id = :g"
                ),
                {"g": group_id},
            )
    with as_user(app_engine, None) as conn:
        assert (
            conn.execute(text("SELECT app_feature_on_for_me('you.journey')")).scalar_one() is False
        )


def test_story_versions_are_kept(people: People, journey_on: None) -> None:
    casey = people.new("Casey")
    start = journey(people, casey)
    assert start["story"] is None
    assert start["history"] == []
    assert start["settings"] == {"ai_consent": False, "onboarding": "new"}
    assert start["learning_days"] == 0

    # Tags from your focus lists when you don't pick any.
    people.client.put(
        "/v1/me/focus",
        json={"strengths": ["serve_consistency"], "improve": ["dinking_patience"]},
        headers=casey,
    )
    first = save(people, casey, **STORY)
    assert first.status_code == 200, first.text
    story = first.json()["story"]
    assert story["gaps"] == STORY["gaps"]
    assert story["tag_strengths"] == ["serve_consistency"]
    assert story["tag_gaps"] == ["dinking_patience"]
    assert story["tags_source"] == "rules"
    assert first.json()["settings"]["onboarding"] == "done"
    assert first.json()["learning_days"] == 1

    second = save(
        people,
        casey,
        **{**STORY, "goal": "  Reset from the transition zone.  "},
        tag_strengths=["footwork"],
        tag_gaps=["transition_resets"],
    ).json()
    assert second["story"]["goal"] == "Reset from the transition zone."
    assert second["story"]["tags_source"] == "player"
    assert [s["goal"] for s in second["history"]] == [STORY["goal"]]
    # Same day, so still one learning day.
    assert second["learning_days"] == 1


@pytest.mark.parametrize(
    "story",
    [
        {},
        {"origin": "   "},
        {"origin": "x" * 801},
        {"goal": "x" * 301},
        {"origin": "hi\x00there"},
        {"origin": "bell\x07"},
        {"origin": "ok", "tag_gaps": ["not_a_skill"]},
        {"origin": "ok", "tag_gaps": ["footwork", "footwork"]},
        {
            "origin": "ok",
            "tag_gaps": ["footwork", "backhand", "lobs_overheads", "poaching", "spin_variety"],
        },
        {"origin": "ok", "tag_strengths": ["footwork"], "tag_gaps": ["footwork"]},
        {"origin": "ok", "mood": "great"},
    ],
)
def test_bad_stories_are_rejected(people: People, journey_on: None, story: dict[str, Any]) -> None:
    casey = people.new("Casey")
    assert save(people, casey, **story).status_code == 422
    assert journey(people, casey)["story"] is None


def test_line_breaks_are_kept(people: People, journey_on: None) -> None:
    casey = people.new("Casey")
    body = save(people, casey, origin="Started in May.\nHooked by June.").json()
    assert body["story"]["origin"] == "Started in May.\nHooked by June."


def test_story_is_private_and_append_only_in_the_database(
    people: People, journey_on: None, app_engine: Engine
) -> None:
    casey = people.new("Casey")
    group_id = create(people, casey)["id"]
    sam = join_and_approve(people, casey, group_id, "Sam")
    save(people, casey, **STORY)
    people.client.post(
        "/v1/me/journey/notes", json={"body": "Soft hands on resets."}, headers=casey
    )
    casey_id, sam_id = people.user_id(casey), people.user_id(sam)
    # A crewmate sees none of it.
    assert journey(people, sam)["story"] is None
    with as_user(app_engine, sam_id) as conn:
        for table in ("journey_entries", "journey_notes", "journey_settings"):
            seen = conn.execute(
                text(f"SELECT count(*) FROM {table} WHERE user_id = :u"), {"u": casey_id}
            ).scalar_one()
            assert seen == 0, table
        assert (
            conn.execute(
                text("DELETE FROM journey_notes WHERE user_id = :u"), {"u": casey_id}
            ).rowcount
            == 0
        )
        state = sqlstate_of(
            conn,
            "INSERT INTO journey_entries (user_id, origin, tags_source) VALUES (:u, 'x', 'player')",
            {"u": casey_id},
        )
        assert state == INSUFFICIENT_PRIVILEGE
        state = sqlstate_of(
            conn,
            "INSERT INTO journey_notes (user_id, body) VALUES (:u, 'x')",
            {"u": casey_id},
        )
        assert state == INSUFFICIENT_PRIVILEGE
        state = sqlstate_of(
            conn,
            "INSERT INTO journey_settings (user_id, ai_consent) VALUES (:u, true)",
            {"u": casey_id},
        )
        assert state == INSUFFICIENT_PRIVILEGE
    # Not even you can change or remove an old version, or move a row to someone else.
    with as_user(app_engine, casey_id) as conn:
        for sql in (
            "UPDATE journey_entries SET goal = 'changed' WHERE user_id = :me",
            "DELETE FROM journey_entries WHERE user_id = :me",
            "UPDATE journey_notes SET body = 'changed' WHERE user_id = :me",
            "UPDATE journey_settings SET user_id = :other WHERE user_id = :me",
        ):
            assert sqlstate_of(conn, sql, {"me": casey_id, "other": sam_id}) == (
                INSUFFICIENT_PRIVILEGE
            ), sql


def test_learning_notes(people: People, journey_on: None) -> None:
    casey = people.new("Casey")
    added = people.client.post(
        "/v1/me/journey/notes",
        json={"body": "  Watched the ball onto the paddle.  ", "skill": "footwork"},
        headers=casey,
    )
    assert added.status_code == 201, added.text
    note = added.json()
    assert note["body"] == "Watched the ball onto the paddle."
    body = journey(people, casey)
    assert [n["id"] for n in body["notes"]] == [note["id"]]
    assert body["learning_days"] == 1

    for bad in (
        {"body": ""},
        {"body": "   "},
        {"body": "x" * 201},
        {"body": "ok", "skill": "juggling"},
        {"body": "ok", "noted_on": (datetime.now(UTC).date() - timedelta(days=3)).isoformat()},
    ):
        response = people.client.post("/v1/me/journey/notes", json=bad, headers=casey)
        assert response.status_code == 422, bad

    # A note from yesterday (your time zone may be behind the server's) counts its own day.
    yesterday = (datetime.now(UTC).date() - timedelta(days=1)).isoformat()
    people.client.post(
        "/v1/me/journey/notes", json={"body": "Split step!", "noted_on": yesterday}, headers=casey
    )
    assert journey(people, casey)["learning_days"] == 2

    # Only your own notes can be deleted.
    sam = people.new("Sam")
    assert (
        people.client.delete(f"/v1/me/journey/notes/{note['id']}", headers=sam).status_code == 404
    )
    assert (
        people.client.delete(f"/v1/me/journey/notes/{note['id']}", headers=casey).status_code == 204
    )
    assert (
        people.client.delete(f"/v1/me/journey/notes/{note['id']}", headers=casey).status_code == 404
    )
    # It counts days with something in them, so deleting a day's only note takes that day.
    assert journey(people, casey)["learning_days"] == 1


def test_daily_limits(people: People, journey_on: None, owner_engine: Engine) -> None:
    casey = people.new("Casey")
    for n in range(10):
        response = people.client.post(
            "/v1/me/journey/notes", json={"body": f"Note {n}"}, headers=casey
        )
        assert response.status_code == 201
    too_many = people.client.post("/v1/me/journey/notes", json={"body": "One more"}, headers=casey)
    assert too_many.status_code == 429
    for n in range(20):
        assert save(people, casey, goal=f"Goal {n}").status_code == 200
    assert save(people, casey, goal="Goal 21").status_code == 429
    # A day later, you can save again.
    with owner_with(owner_engine, "journey_entries", "UPDATE") as conn:
        conn.execute(
            text(
                "UPDATE journey_entries SET created_at = created_at - interval '25 hours' "
                "WHERE user_id = :u"
            ),
            {"u": people.user_id(casey)},
        )
    assert save(people, casey, goal="Tomorrow's goal").status_code == 200
    # The app shows the latest 21 versions; all are kept.
    body = journey(people, casey)
    assert body["story"]["goal"] == "Tomorrow's goal"
    assert len(body["history"]) == 20


def test_settings(people: People, journey_on: None) -> None:
    casey = people.new("Casey")
    response = people.client.put(
        "/v1/me/journey/settings", json={"onboarding": "skipped"}, headers=casey
    )
    assert response.json() == {"ai_consent": False, "onboarding": "skipped"}
    response = people.client.put(
        "/v1/me/journey/settings", json={"ai_consent": True}, headers=casey
    )
    assert response.json() == {"ai_consent": True, "onboarding": "skipped"}
    for bad in ({"onboarding": "new"}, {"ai_consent": "yes"}, {"colour": "green"}):
        assert (
            people.client.put("/v1/me/journey/settings", json=bad, headers=casey).status_code == 422
        ), bad
    # Saving your story marks onboarding done and leaves consent as it was.
    after = save(people, casey, **STORY).json()["settings"]
    assert after == {"ai_consent": True, "onboarding": "done"}


def test_in_your_data_download(people: People, journey_on: None) -> None:
    casey = people.new("Casey")
    save(people, casey, **STORY)
    save(people, casey, **{**STORY, "goal": "A new goal"})
    people.client.post("/v1/me/journey/notes", json={"body": "Patience."}, headers=casey)
    data = people.client.get("/v1/me/export", headers=casey).json()["journey"]
    assert [s["goal"] for s in data["stories"]] == [STORY["goal"], "A new goal"]
    assert [n["body"] for n in data["learning_notes"]] == ["Patience."]
    assert data["settings"] == {"ai_consent": False, "onboarding": "done"}
    # Someone else's file has none of it.
    other = people.client.get("/v1/me/export", headers=people.new("Sam")).json()["journey"]
    assert other == {"stories": [], "learning_notes": [], "settings": None}


def journey_rows(owner_engine: Engine, user_id: UUID) -> int:
    with owner(owner_engine) as conn:
        count: int = conn.execute(
            text(
                "SELECT (SELECT count(*) FROM journey_entries WHERE user_id = :u)"
                " + (SELECT count(*) FROM journey_notes WHERE user_id = :u)"
                " + (SELECT count(*) FROM journey_settings WHERE user_id = :u)"
            ),
            {"u": user_id},
        ).scalar_one()
    return count


def test_a_deleted_account_takes_its_journey_with_it(
    people: People, journey_on: None, owner_engine: Engine
) -> None:
    casey, sam = people.new("Casey"), people.new("Sam")
    for who in (casey, sam):
        save(people, who, **STORY)
        people.client.post("/v1/me/journey/notes", json={"body": "Patience."}, headers=who)
    casey_id, sam_id = people.user_id(casey), people.user_id(sam)
    assert journey_rows(owner_engine, casey_id) == 3
    with owner(owner_engine) as conn:
        conn.execute(text("UPDATE users SET deleted_at = now() WHERE id = :u"), {"u": casey_id})
    assert journey_rows(owner_engine, casey_id) == 0
    assert journey_rows(owner_engine, sam_id) == 3
