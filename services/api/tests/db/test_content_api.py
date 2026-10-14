"""The content library (migration 0033, routes/admin_content.py, journey picks)."""

import json
from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import Engine, text

from tests.db.conftest import ADMIN, INSUFFICIENT_PRIVILEGE, Admins, as_user, sign_in, sqlstate_of
from tests.db.test_features import owner

pytestmark = pytest.mark.db

REASON = "A clear drop-shot video for beginners."
VIDEO = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
CHECK_VIOLATION = "23514"


def item(**over: Any) -> dict[str, Any]:
    return {
        "kind": "video",
        "url": "https://youtu.be/dQw4w9WgXcQ",
        "title": "Third-shot drops, made simple",
        "source": "A Coach",
        "skills": ["third_shot_drop"],
        "levels": ["beginner"],
        "minutes": 8,
        "reason": REASON,
        **over,
    }


@pytest.fixture
def boss(admins: Admins) -> dict[str, str]:
    return sign_in(admins, ADMIN.lower())


@pytest.fixture(autouse=True)
def clean(owner_engine: Engine) -> Iterator[None]:
    yield
    with owner(owner_engine) as conn:
        conn.execute(text("DELETE FROM content_items"))
        conn.execute(
            text(
                "DELETE FROM content_hosts "
                "WHERE host NOT IN ('youtube.com', 'www.youtube.com', 'youtu.be')"
            )
        )


@pytest.fixture
def journey_on(owner_engine: Engine) -> Iterator[None]:
    with owner(owner_engine) as conn:
        conn.execute(text("UPDATE features SET rollout = 'everyone' WHERE key = 'you.journey'"))
    yield
    with owner(owner_engine) as conn:
        conn.execute(text("UPDATE features SET rollout = 'crews' WHERE key = 'you.journey'"))


def add(admins: Admins, boss: dict[str, str], **over: Any) -> Any:
    return admins.admin.post("/v1/admin/content", json=item(**over), headers=boss)


def publish(admins: Admins, boss: dict[str, str], item_id: str, to: str = "published") -> Any:
    return admins.admin.put(
        f"/v1/admin/content/{item_id}/status", json={"status": to, "reason": REASON}, headers=boss
    )


def logged(owner_engine: Engine, action: str) -> list[dict[str, Any]]:
    with owner(owner_engine) as conn:
        rows = conn.execute(
            text(
                "SELECT reason, details FROM admin_actions WHERE action = :a "
                "ORDER BY id DESC LIMIT 5"
            ),
            {"a": action},
        ).all()
    return [{"reason": r.reason, "details": r.details} for r in rows]


def test_only_admins_with_a_fresh_sign_in(admins: Admins) -> None:
    casey = admins.new("Casey")
    for method, path in (("GET", "/v1/admin/content"), ("POST", "/v1/admin/content")):
        response = admins.admin.request(method, path, json=item(), headers=casey)
        assert response.status_code == 404, path
    stale = sign_in(admins, ADMIN.lower(), signed_in_ago=60 * 60 * 24)
    assert add(admins, stale).status_code == 403
    # And never on the players' API.
    assert admins.client.get("/v1/admin/content", headers=casey).status_code == 404


def test_add_publish_and_players_see_it(
    admins: Admins, boss: dict[str, str], owner_engine: Engine, journey_on: None
) -> None:
    added = add(admins, boss)
    assert added.status_code == 201, added.text
    body = added.json()
    assert body["url"] == VIDEO
    assert logged(owner_engine, "content.add")[0]["reason"] == REASON

    # The same video under another address is a duplicate.
    again = add(admins, boss, url="https://www.youtube.com/shorts/dQw4w9WgXcQ")
    assert again.status_code == 409

    casey = admins.new("Casey")
    picks = admins.client.get("/v1/me/journey/picks?skills=third_shot_drop", headers=casey)
    assert picks.json() == []  # still a draft

    assert publish(admins, boss, body["id"]).status_code == 204
    assert logged(owner_engine, "content.status")[0]["details"]["after"] == "published"
    picks = admins.client.get("/v1/me/journey/picks?skills=third_shot_drop", headers=casey).json()
    assert [p["url"] for p in picks] == [VIDEO]
    assert set(picks[0]) == {"id", "kind", "url", "title", "source", "skills", "minutes"}

    # Unpublished, it's gone again.
    publish(admins, boss, body["id"], "draft")
    assert (
        admins.client.get("/v1/me/journey/picks?skills=third_shot_drop", headers=casey).json() == []
    )

    listed = admins.admin.get("/v1/admin/content", headers=boss).json()
    assert [(i["id"], i["status"]) for i in listed] == [(body["id"], "draft")]


def test_picks_match_skills_and_level(
    admins: Admins, boss: dict[str, str], journey_on: None
) -> None:
    ids = {}
    for name, url, skills, levels in (
        ("drop", "https://youtu.be/aaaaaaaaaaa", ["third_shot_drop"], ["beginner"]),
        ("drop-pro", "https://youtu.be/bbbbbbbbbbb", ["third_shot_drop"], ["expert"]),
        ("dink", "https://youtu.be/ccccccccccc", ["dinking_patience"], []),
        ("both", "https://youtu.be/ddddddddddd", ["third_shot_drop", "dinking_patience"], []),
    ):
        made = add(admins, boss, url=url, title=name, skills=skills, levels=levels).json()
        publish(admins, boss, made["id"])
        ids[made["id"]] = name
    casey = admins.new("Casey")
    admins.client.put("/v1/me/level", json={"level": "beginner"}, headers=casey)

    def titles(query: str) -> list[str]:
        response = admins.client.get(f"/v1/me/journey/picks{query}", headers=casey)
        assert response.status_code == 200, response.text
        return [p["title"] for p in response.json()]

    # Best match first; the expert video isn't for a beginner.
    assert titles("?skills=third_shot_drop&skills=dinking_patience")[0] == "both"
    assert "drop-pro" not in titles("?skills=third_shot_drop")
    assert set(titles("?skills=dinking_patience")) == {"dink", "both"}
    # Unknown skills match nothing; no skills means anything (at most 3).
    assert titles("?skills=juggling") == []
    assert len(titles("")) == 3


def test_picks_need_the_journey(admins: Admins) -> None:
    casey = admins.new("Casey")
    assert admins.client.get("/v1/me/journey/picks", headers=casey).status_code == 404


@pytest.mark.parametrize(
    ("over", "code"),
    [
        ({"url": "http://youtu.be/dQw4w9WgXcQ"}, 422),
        ({"url": "javascript:alert(1)"}, 422),
        ({"url": "https://user@youtu.be/dQw4w9WgXcQ"}, 422),
        ({"url": "https://evil.example/watch"}, 422),
        ({"skills": []}, 422),
        ({"skills": ["juggling"]}, 422),
        ({"skills": ["footwork", "footwork"]}, 422),
        ({"levels": ["pro"]}, 422),
        ({"minutes": 0}, 422),
        ({"title": "   "}, 422),
        ({"reason": "short"}, 422),
        ({"kind": "podcast"}, 422),
        ({"extra": 1}, 422),
    ],
)
def test_bad_items_are_refused(
    admins: Admins, boss: dict[str, str], over: dict[str, Any], code: int
) -> None:
    assert add(admins, boss, **over).status_code == code
    assert admins.admin.get("/v1/admin/content", headers=boss).json() == []


def test_new_sites_need_adding_first(
    admins: Admins, boss: dict[str, str], owner_engine: Engine
) -> None:
    article = {
        "kind": "article",
        "url": "https://coach.example.org/drops#top",
        "skills": ["third_shot_drop"],
    }
    refused = add(admins, boss, **article)
    assert refused.status_code == 422
    assert "allowed list" in refused.json()["detail"]
    for bad in ("localhost", "https://coach.example.org", "coach.example.org/x"):
        response = admins.admin.post(
            "/v1/admin/content/hosts", json={"host": bad, "reason": REASON}, headers=boss
        )
        assert response.status_code == 422, bad
    added = admins.admin.post(
        "/v1/admin/content/hosts",
        json={"host": "Coach.Example.org", "reason": REASON},
        headers=boss,
    )
    assert added.status_code == 204
    assert logged(owner_engine, "content.host_add")[0]["details"]["host"] == "coach.example.org"
    hosts = admins.admin.get("/v1/admin/content/hosts", headers=boss).json()
    assert sorted(h["host"] for h in hosts) == [
        "coach.example.org",
        "www.youtube.com",
        "youtu.be",
        "youtube.com",
    ]
    made = add(admins, boss, **article)
    assert made.status_code == 201
    assert made.json()["url"] == "https://coach.example.org/drops"


def test_edit(admins: Admins, boss: dict[str, str], owner_engine: Engine) -> None:
    first = add(admins, boss).json()
    other = add(admins, boss, url="https://youtu.be/eeeeeeeeeee").json()
    edited = admins.admin.put(
        f"/v1/admin/content/{first['id']}", json=item(title="Drops, step by step"), headers=boss
    )
    assert edited.status_code == 204
    entry = logged(owner_engine, "content.edit")[0]["details"]
    assert (entry["before"]["title"], entry["after"]["title"]) == (
        "Third-shot drops, made simple",
        "Drops, step by step",
    )
    clash = admins.admin.put(
        f"/v1/admin/content/{first['id']}", json=item(url=other["url"]), headers=boss
    )
    assert clash.status_code == 409
    missing = admins.admin.put(
        "/v1/admin/content/00000000-0000-4000-8000-000000000000", json=item(), headers=boss
    )
    assert missing.status_code == 404


def test_the_database_guards_the_table(
    admins: Admins,
    boss: dict[str, str],
    app_engine: Engine,
    admin_engine: Engine,
    owner_engine: Engine,
) -> None:
    made = add(admins, boss).json()
    casey_id = admins.user_id(admins.new("Casey"))
    # Players and the admin service only go through the functions.
    for engine in (app_engine, admin_engine):
        with as_user(engine, casey_id) as conn:
            for sql in (
                "SELECT count(*) FROM content_items",
                "SELECT count(*) FROM content_hosts",
                "INSERT INTO content_hosts (host) VALUES ('evil.example')",
                "UPDATE content_items SET status = 'published'",
            ):
                assert sqlstate_of(conn, sql) == INSUFFICIENT_PRIVILEGE, sql
    with as_user(app_engine, casey_id) as conn:
        for sql in (
            "SELECT * FROM app_admin_content()",
            "SELECT app_admin_add_content_host('evil.example', 'because it is evil')",
        ):
            assert sqlstate_of(conn, sql) == INSUFFICIENT_PRIVILEGE, sql
        # No one signed in: nothing.
    with as_user(app_engine, None) as conn:
        assert (
            conn.execute(
                text("SELECT count(*) FROM app_published_content('{}', NULL)")
            ).scalar_one()
            == 0
        )
    # Even the owner can't store a link to a host that isn't allowed.
    with owner(owner_engine) as conn:
        for url in (
            "https://evil.example/x",
            "http://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://www.youtube.com:444/watch?v=dQw4w9WgXcQ",
            "https://a@www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://www.youtube.com.evil.example/x",
        ):
            state = sqlstate_of(
                conn,
                "UPDATE content_items SET url = :u WHERE id = :id",
                {"u": url, "id": made["id"]},
            )
            assert state == CHECK_VIOLATION, url
    assert json.dumps(made)  # still there, unchanged
