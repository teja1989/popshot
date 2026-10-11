"""The admin service's overview (migrations 0010 and 0012, routes/admin.py, admin_main.py):
who gets in, and what they see."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from popshot_api.admin_main import create_admin_app
from popshot_api.routes.admin import RECENT_SIGN_IN
from tests.conftest import make_settings
from tests.db.conftest import (
    ADMIN,
    INSUFFICIENT_PRIVILEGE,
    Admins,
    People,
    as_user,
    create,
    sign_in,
    sign_in_as,
    sqlstate_of,
)

pytestmark = pytest.mark.db

PAGES = ["/v1/admin/overview", "/v1/admin/groups"]


def user_exists(owner_engine: Engine, subject: str) -> bool:
    with owner_engine.connect() as conn:
        found = conn.execute(
            text("SELECT count(*) FROM users WHERE auth_subject = :s"), {"s": subject}
        )
        return bool(found.scalar_one())


@pytest.mark.parametrize("path", PAGES)
def test_everyone_else_gets_not_found(admins: Admins, owner_engine: Engine, path: str) -> None:
    unknown = admins.admin.get("/v1/admin/nothing-here", headers=sign_in(admins, "x@example.com"))
    someone, subject = sign_in_as(admins, "casey@example.com")
    response = admins.admin.get(path, headers=someone)
    # Exactly what a path that doesn't exist looks like.
    assert response.status_code == 404
    assert response.json() == unknown.json() == {"detail": "Not Found"}
    # Turned away before the database: not even signed up.
    assert not user_exists(owner_engine, subject)


@pytest.mark.parametrize("path", PAGES)
def test_signed_out_is_401(admins: Admins, path: str) -> None:
    assert admins.admin.get(path).status_code == 401


def test_nobody_is_an_admin_by_default(people: People, admin_engine: Engine) -> None:
    app = create_admin_app(make_settings(), people.verifier, admin_engine)
    with TestClient(app) as admin:
        response = admin.get(PAGES[0], headers=sign_in(people, ADMIN.lower()))
    assert response.status_code == 404


@pytest.mark.parametrize("path", PAGES)
def test_the_main_api_has_no_admin_pages(admins: Admins, path: str) -> None:
    response = admins.client.get(path, headers=sign_in(admins, ADMIN.lower()))
    assert response.status_code == 404


def test_an_admin_must_have_signed_in_recently(admins: Admins) -> None:
    stale = sign_in(admins, ADMIN.lower(), signed_in_ago=RECENT_SIGN_IN + 60)
    response = admins.admin.get(PAGES[0], headers=stale)
    assert response.status_code == 403
    assert response.json() == {"detail": "Sign in again to open the admin page."}


def test_the_overview(admins: Admins, owner_engine: Engine) -> None:
    casey = admins.new("Casey")
    create(admins, casey, "Thursday Smashers")
    boss, subject = sign_in_as(admins, ADMIN.upper())
    response = admins.admin.get("/v1/admin/overview", headers=boss)
    assert response.status_code == 200
    body = response.json()
    totals = body["totals"]
    # Counts across the whole test database, so at least what this test made.
    assert totals["users"] >= 2
    assert totals["active_users_7d"] >= 2
    assert totals["live_groups"] >= 1
    assert len(body["weeks"]) == 12
    assert body["weeks"][-1]["active_users"] >= 2
    assert len(body["retention"]) >= 1
    # The view is recorded.
    with owner_engine.connect() as conn:
        pages = conn.execute(
            text(
                "SELECT v.page FROM admin_views v JOIN users u ON u.id = v.user_id "
                "WHERE u.auth_subject = :s"
            ),
            {"s": subject},
        ).scalars()
        assert list(pages) == ["overview"]


def test_the_groups(admins: Admins) -> None:
    casey = admins.new("Casey")
    group_id = create(admins, casey, "Thursday Smashers")["id"]
    response = admins.admin.get("/v1/admin/groups", headers=sign_in(admins, ADMIN.lower()))
    assert response.status_code == 200
    mine = next(g for g in response.json() if g["id"] == group_id)
    assert mine["name"] == "Thursday Smashers"
    assert (mine["members"], mine["games"], mine["games_30d"], mine["upcoming_nights"]) == (
        1,
        0,
        0,
        0,
    )
    assert mine["last_game_at"] is None
    # Counts and names only: no people.
    assert set(mine) == {
        "id",
        "name",
        "created_at",
        "members",
        "games",
        "games_30d",
        "last_game_at",
        "upcoming_nights",
    }


def test_only_the_admin_service_records_views_and_only_its_own(
    people: People, app_engine: Engine, admin_engine: Engine
) -> None:
    casey = people.user_id(people.new("Casey"))
    sam = people.user_id(people.new("Sam"))
    insert = "INSERT INTO admin_views (user_id, page) VALUES (:u, 'overview')"
    with as_user(app_engine, casey) as conn:
        assert sqlstate_of(conn, insert, {"u": casey}) == INSUFFICIENT_PRIVILEGE
    with as_user(admin_engine, casey) as conn:
        assert sqlstate_of(conn, "SELECT count(*) FROM admin_views") == INSUFFICIENT_PRIVILEGE
        assert sqlstate_of(conn, insert, {"u": sam}) == INSUFFICIENT_PRIVILEGE
        assert sqlstate_of(conn, insert, {"u": casey}) is None


@pytest.mark.parametrize(
    "call",
    [
        "app_admin_totals()",
        "app_admin_groups()",
        "app_metrics_weekly(4)",
        "app_metrics_retention(4)",
        "app_admin_people('x', NULL)",
        "app_admin_person(gen_random_uuid())",
        "app_admin_person_groups(gen_random_uuid())",
        "app_admin_group(gen_random_uuid())",
        "app_admin_group_members(gen_random_uuid())",
    ],
)
def test_the_main_api_cannot_call_admin_functions(
    people: People, app_engine: Engine, admin_engine: Engine, call: str
) -> None:
    casey = people.user_id(people.new("Casey"))
    with as_user(app_engine, casey) as conn:
        assert sqlstate_of(conn, f"SELECT * FROM {call}") == INSUFFICIENT_PRIVILEGE
    with as_user(admin_engine, casey) as conn:
        assert sqlstate_of(conn, f"SELECT * FROM {call}") is None
