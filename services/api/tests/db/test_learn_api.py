"""Learn shots (migration 0029): admins write and publish them, anyone reads published ones."""

import copy
import secrets
from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import Engine, text

from popshot_api.routes import admin_learn
from popshot_api.routes.admin_actions import FRESH_SIGN_IN
from tests.db.conftest import ADMIN, INSUFFICIENT_PRIVILEGE, Admins, as_user, sign_in, sqlstate_of
from tests.db.test_admin_features_api import logged
from tests.db.test_features import owner
from tests.test_learn_scene import good_scene

pytestmark = pytest.mark.db

REASON = "First shots for the Learn pages."
SHOTS = "/v1/admin/learn/shots"
PUBLIC = "/v1/public/learn/shots"


class Learn:
    def __init__(self, owner_engine: Engine) -> None:
        self.owner_engine = owner_engine
        self.slugs: list[str] = []
        with owner(owner_engine) as conn:
            self.was = conn.execute(
                text("SELECT rollout FROM features WHERE key = 'learn.public'")
            ).scalar_one()

    def slug(self) -> str:
        made = f"test-{secrets.token_hex(4)}"
        self.slugs.append(made)
        return made

    def public(self, rollout: str) -> None:
        with owner(self.owner_engine) as conn:
            conn.execute(
                text("UPDATE features SET rollout = :r WHERE key = 'learn.public'"), {"r": rollout}
            )

    def cleanup(self) -> None:
        self.public(self.was)
        with owner(self.owner_engine) as conn:
            conn.execute(text("DELETE FROM shots WHERE slug = ANY(:s)"), {"s": self.slugs})


@pytest.fixture
def learn(owner_engine: Engine) -> Iterator[Learn]:
    made = Learn(owner_engine)
    yield made
    made.cleanup()


@pytest.fixture
def boss(admins: Admins) -> dict[str, str]:
    return sign_in(admins, ADMIN.lower())


def fields(slug: str, **changes: Any) -> dict[str, Any]:
    return {
        "slug": slug,
        "title": "Third-shot drop",
        "summary": "Take the net back with a soft shot that lands in their kitchen.",
        "level": "intermediate",
        "focus_ids": ["third_shot_drop", "getting_to_kitchen"],
        "tips": ["Lift from low to high.", "Follow it in."],
        "drill_steps": ["Ten drops cross-court.", "Then ten straight on."],
        "scene": good_scene(),
        **changes,
    }


def create(admins: Admins, boss: dict[str, str], slug: str, **changes: Any) -> str:
    made = admins.admin.post(
        SHOTS, json={**fields(slug, **changes), "reason": REASON}, headers=boss
    )
    assert made.status_code == 201, made.text
    shot_id: str = made.json()["id"]
    return shot_id


def publish(admins: Admins, boss: dict[str, str], shot_id: str, version: int) -> Any:
    return admins.admin.post(
        f"{SHOTS}/{shot_id}/publish", json={"version": version, "reason": REASON}, headers=boss
    )


def test_everyone_else_gets_not_found(admins: Admins, learn: Learn, boss: dict[str, str]) -> None:
    shot_id = create(admins, boss, learn.slug())
    casey = admins.new("Casey")
    for method, path, body in (
        ("GET", SHOTS, None),
        ("GET", f"{SHOTS}/{shot_id}", None),
        ("POST", SHOTS, {**fields(learn.slug()), "reason": REASON}),
        ("PUT", f"{SHOTS}/{shot_id}", {**fields(learn.slug()), "version": 1}),
        ("POST", f"{SHOTS}/{shot_id}/publish", {"version": 1, "reason": REASON}),
        ("POST", f"{SHOTS}/{shot_id}/delete", {"reason": REASON}),
    ):
        response = admins.admin.request(method, path, json=body, headers=casey)
        assert (response.status_code, response.json()) == (404, {"detail": "Not Found"}), path
    # The main API has no admin routes at all.
    assert admins.client.get(SHOTS, headers=boss).status_code == 404


def test_changes_need_a_recent_sign_in_and_reasons(
    admins: Admins, learn: Learn, boss: dict[str, str], owner_engine: Engine
) -> None:
    stale = sign_in(admins, ADMIN.lower(), signed_in_ago=FRESH_SIGN_IN + 60)
    slug = learn.slug()
    body = {**fields(slug), "reason": REASON}
    assert admins.admin.post(SHOTS, json=body, headers=stale).status_code == 403
    assert admins.admin.get(SHOTS, headers=stale).status_code == 200
    for missing in ({**fields(slug)}, {**fields(slug), "reason": "short"}):
        assert admins.admin.post(SHOTS, json=missing, headers=boss).status_code == 422
    shot_id = create(admins, boss, slug)
    path = f"{SHOTS}/{shot_id}"
    assert (
        admins.admin.put(path, json={**fields(slug), "version": 1}, headers=stale).status_code
        == 403
    )
    for action in ("publish", "unpublish", "delete"):
        assert (
            admins.admin.post(
                f"{path}/{action}", json={"version": 1, "reason": REASON}, headers=stale
            ).status_code
            == 403
        ), action
        no_reason = admins.admin.post(f"{path}/{action}", json={"version": 1}, headers=boss)
        assert no_reason.status_code == 422, action
    assert logged(owner_engine, "learn.publish", slug=slug) == []
    assert [e["details"]["after"] for e in logged(owner_engine, "learn.create", shot=shot_id)] == [
        {"slug": slug}
    ]


@pytest.mark.parametrize(
    "changes",
    [
        {"slug": "Has Spaces"},
        {"slug": "dots.in.it"},
        {"slug": "-leading"},
        {"slug": "x" * 61},
        {"title": ""},
        {"title": "x" * 61},
        {"summary": "x" * 201},
        {"level": "pro"},
        {"focus_ids": []},
        {"focus_ids": ["not_a_focus"]},
        {"focus_ids": ["third_shot_drop", "third_shot_drop"]},
        {"focus_ids": ["footwork", "backhand", "poaching", "lobs_overheads", "put_aways"]},
        {"tips": ["x" * 201]},
        {"tips": ["Tip"] * 9},
        {"tips": [""]},
        {"drill_steps": ["Step"] * 11},
        {"scene": {**good_scene(), "duration": 99}},
        {"scene": {**good_scene(), "html": "<script>"}},
        {"extra": 1},
    ],
)
def test_bad_shots_are_refused(
    admins: Admins, learn: Learn, boss: dict[str, str], changes: dict[str, Any]
) -> None:
    body = {**fields(learn.slug()), **changes, "reason": REASON}
    assert admins.admin.post(SHOTS, json=body, headers=boss).status_code == 422, changes


def test_a_scene_too_big_is_refused(
    admins: Admins, learn: Learn, boss: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    # Every scene within the shape's own limits fits in 32 KB, so try a smaller limit.
    monkeypatch.setattr(admin_learn, "MAX_SCENE_BYTES", 1000)
    response = admins.admin.post(
        SHOTS, json={**fields(learn.slug()), "reason": REASON}, headers=boss
    )
    assert response.status_code == 422
    assert "too big" in response.text


def test_draft_publish_edit_and_unpublish(
    admins: Admins, learn: Learn, boss: dict[str, str], owner_engine: Engine
) -> None:
    learn.public("everyone")
    slug = learn.slug()
    shot_id = create(admins, boss, slug)
    # Drafts are never public.
    assert slug not in [s["slug"] for s in admins.client.get(PUBLIC).json()]
    assert admins.client.get(f"{PUBLIC}/{slug}").status_code == 404

    assert publish(admins, boss, shot_id, 1).status_code == 204
    listed = {s["slug"]: s for s in admins.client.get(PUBLIC).json()}
    assert listed[slug]["title"] == "Third-shot drop"
    assert listed[slug]["focus"][0] == {
        "id": "third_shot_drop",
        "label": "Third-shot drops",
        "area": "Third shot",
    }
    shot = admins.client.get(f"{PUBLIC}/{slug}").json()
    assert shot["tips"] == ["Lift from low to high.", "Follow it in."]
    assert shot["scene"]["flights"][2]["kind"] == "drop"
    assert "version" not in shot
    assert "id" not in shot

    # Edits stay private until published again.
    path = f"{SHOTS}/{shot_id}"
    saved = admins.admin.put(
        path, json={**fields(slug, title="Soft third"), "version": 1}, headers=boss
    )
    assert saved.status_code == 200, saved.text
    assert (saved.json()["version"], saved.json()["published_version"]) == (2, 1)
    assert admins.client.get(f"{PUBLIC}/{slug}").json()["title"] == "Third-shot drop"
    # Publishing the same version twice changes nothing and isn't logged twice.
    assert publish(admins, boss, shot_id, 2).status_code == 204
    assert publish(admins, boss, shot_id, 2).status_code == 204
    assert admins.client.get(f"{PUBLIC}/{slug}").json()["title"] == "Soft third"
    assert [e["details"]["after"] for e in logged(owner_engine, "learn.publish", slug=slug)] == [
        1,
        2,
    ]

    # Published, the address is fixed.
    moved = admins.admin.put(
        path, json={**fields(learn.slug(), title="Soft third"), "version": 2}, headers=boss
    )
    assert (moved.status_code, moved.json()["detail"]) == (
        409,
        "This shot has been published, so its address can't change.",
    )
    # A published shot can't be deleted.
    gone = admins.admin.post(f"{path}/delete", json={"reason": REASON}, headers=boss)
    assert gone.status_code == 409

    off = admins.admin.post(f"{path}/unpublish", json={"reason": REASON}, headers=boss)
    assert off.status_code == 204
    assert admins.client.get(f"{PUBLIC}/{slug}").status_code == 404
    assert slug not in [s["slug"] for s in admins.client.get(PUBLIC).json()]
    # Still fixed after unpublishing: links to it may be out there.
    assert admins.admin.get(path, headers=boss).json()["slug_locked"] is True
    assert (
        admins.admin.post(f"{path}/delete", json={"reason": REASON}, headers=boss).status_code
        == 204
    )
    assert admins.admin.get(path, headers=boss).status_code == 404
    assert [e["action"] for e in _actions(owner_engine, shot_id)] == [
        "learn.create",
        "learn.publish",
        "learn.publish",
        "learn.unpublish",
        "learn.delete",
    ]


def _actions(owner_engine: Engine, shot_id: str) -> list[dict[str, Any]]:
    with owner(owner_engine) as conn:
        rows = conn.execute(
            text(
                "SELECT action, reason FROM admin_actions WHERE details->>'shot' = :s ORDER BY id"
            ),
            {"s": shot_id},
        ).all()
    return [{"action": r.action, "reason": r.reason} for r in rows]


def test_the_switch_hides_everything(admins: Admins, learn: Learn, boss: dict[str, str]) -> None:
    slug = learn.slug()
    shot_id = create(admins, boss, slug)
    assert publish(admins, boss, shot_id, 1).status_code == 204
    for rollout, shown in (("off", False), ("crews", False), ("everyone", True), ("off", False)):
        learn.public(rollout)
        assert (admins.client.get(f"{PUBLIC}/{slug}").status_code == 200) is shown, rollout
        assert (slug in [s["slug"] for s in admins.client.get(PUBLIC).json()]) is shown, rollout


def test_saves_and_publishes_must_be_of_the_latest_version(
    admins: Admins, learn: Learn, boss: dict[str, str]
) -> None:
    slug = learn.slug()
    shot_id = create(admins, boss, slug)
    path = f"{SHOTS}/{shot_id}"
    first = admins.admin.put(path, json={**fields(slug, title="One"), "version": 1}, headers=boss)
    assert first.status_code == 200
    late = admins.admin.put(path, json={**fields(slug, title="Two"), "version": 1}, headers=boss)
    assert late.status_code == 409
    assert "Reload" in late.json()["detail"]
    assert admins.admin.get(path, headers=boss).json()["title"] == "One"
    assert publish(admins, boss, shot_id, 1).status_code == 409
    assert admins.admin.get(path, headers=boss).json()["published_version"] is None
    taken = create(admins, boss, learn.slug())
    clash = admins.admin.put(f"{SHOTS}/{taken}", json={**fields(slug), "version": 1}, headers=boss)
    assert (clash.status_code, clash.json()["detail"]) == (
        409,
        "Another shot already has that address.",
    )
    again = admins.admin.post(SHOTS, json={**fields(slug), "reason": REASON}, headers=boss)
    assert again.status_code == 409


def test_a_shot_with_problems_cant_be_published(
    admins: Admins, learn: Learn, boss: dict[str, str], owner_engine: Engine
) -> None:
    scene = copy.deepcopy(good_scene())
    scene["flights"][2]["start"] = {"x": 10, "y": 3, "z": 1}
    scene["flights"][2]["apex_z"] = 1
    slug = learn.slug()
    # Saving a draft with problems is fine: you fix them as you go.
    shot_id = create(admins, boss, slug, scene=scene)
    shot = admins.admin.get(f"{SHOTS}/{shot_id}", headers=boss).json()
    assert [(p["code"], p["flight"]) for p in shot["problems"]] == [("net", 2)]
    refused = publish(admins, boss, shot_id, 1)
    assert (refused.status_code, refused.json()["detail"]) == (422, "Shot 3 hits the net.")
    assert logged(owner_engine, "learn.publish", slug=slug) == []
    assert admins.admin.get(f"{SHOTS}/{shot_id}", headers=boss).json()["published_at"] is None


def test_public_slugs_are_checked(admins: Admins, learn: Learn) -> None:
    learn.public("everyone")
    for bad in ("Upper", "x" * 61, "a--b", "a_b"):
        assert admins.client.get(f"{PUBLIC}/{bad}").status_code == 422, bad
    assert admins.client.get(f"{PUBLIC}/no-such-shot").json() == {
        "detail": "We couldn't find that shot."
    }


def test_only_the_functions_touch_shots(
    admins: Admins, app_engine: Engine, admin_engine: Engine, boss: dict[str, str], learn: Learn
) -> None:
    shot_id = create(admins, boss, learn.slug())
    me = admins.user_id(boss)
    for engine in (app_engine, admin_engine):
        with as_user(engine, me) as conn:
            for statement in (
                "SELECT count(*) FROM shots",
                "UPDATE shots SET title = 'x'",
                "DELETE FROM shots",
                "SELECT app_learn_public()",
            ):
                assert sqlstate_of(conn, statement) == INSUFFICIENT_PRIVILEGE, statement
    with as_user(app_engine, me) as conn:
        for call in (
            "SELECT * FROM app_admin_shots()",
            "SELECT * FROM app_admin_shot(:id)",
            "SELECT app_admin_publish_shot(:id, 1, 'a reason long enough')",
            "SELECT app_admin_unpublish_shot(:id, 'a reason long enough')",
            "SELECT app_admin_delete_shot(:id, 'a reason long enough')",
        ):
            assert sqlstate_of(conn, call, {"id": shot_id}) == INSUFFICIENT_PRIVILEGE, call
    # With no one signed in, the admin functions refuse even for the admin login.
    with as_user(admin_engine, None) as conn:
        assert (
            sqlstate_of(
                conn, "SELECT app_admin_delete_shot(:id, 'a reason long enough')", {"id": shot_id}
            )
            == INSUFFICIENT_PRIVILEGE
        )


def test_the_database_checks_versions_itself(
    admins: Admins, admin_engine: Engine, boss: dict[str, str], learn: Learn
) -> None:
    """The API checks first, but the functions check again under a lock, for two admins at
    once."""
    shot_id = create(admins, boss, learn.slug())
    me = admins.user_id(boss)
    with as_user(admin_engine, me) as conn:
        for call in (
            "SELECT app_admin_publish_shot(:id, 2, 'a reason long enough')",
            "SELECT app_admin_save_shot(:id, 2, 'a-slug', 'T', 'S', 'beginner', "
            "ARRAY['footwork'], ARRAY[]::text[], ARRAY[]::text[], '{}'::jsonb)",
        ):
            assert conn.execute(text(call), {"id": shot_id}).scalar_one() == "stale", call
        assert (
            conn.execute(
                text("SELECT app_admin_publish_shot(:id, 1, 'a reason long enough')"),
                {"id": shot_id},
            ).scalar_one()
            == "done"
        )
        assert (
            conn.execute(
                text(
                    "SELECT app_admin_save_shot(:id, 1, 'moved-away', 'T', 'S', 'beginner', "
                    "ARRAY['footwork'], ARRAY[]::text[], ARRAY[]::text[], '{}'::jsonb)"
                ),
                {"id": shot_id},
            ).scalar_one()
            == "slug_locked"
        )
