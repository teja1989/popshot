"""The admin page's API (migration 0010, routes/admin.py): who gets in, and what they see."""

import secrets
import time
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from popshot_api.auth.verifier import VerifiedIdentity
from popshot_api.main import create_app
from popshot_api.routes.admin import RECENT_SIGN_IN
from tests.conftest import make_settings
from tests.db.conftest import INSUFFICIENT_PRIVILEGE, People, as_user, create, sqlstate_of
from tests.fakes import FakeTokenVerifier

pytestmark = pytest.mark.db

ADMIN = "Boss@Example.com"
PAGES = ["/v1/admin/overview", "/v1/admin/groups"]


@pytest.fixture
def admins(app_engine: Engine) -> Iterator[People]:
    """Like `people`, with boss@example.com as the admin (set with different case)."""
    verifier = FakeTokenVerifier()
    app = create_app(make_settings(admin_emails=f" {ADMIN} , "), verifier, app_engine)
    with TestClient(app) as client:
        yield People(client, verifier)


def sign_in_as(
    people: People, email: str, *, signed_in_ago: int = 60
) -> tuple[dict[str, str], str]:
    """Headers for a new person with this email, and their token subject."""
    token = f"token-{secrets.token_hex(8)}"
    subject = f"admin-test-{secrets.token_hex(8)}"
    people.verifier.identities[token] = VerifiedIdentity(
        subject=subject,
        email=email,
        display_name="Admin Test",
        picture_url=None,
        auth_time=int(time.time()) - signed_in_ago,
    )
    return {"Authorization": f"Bearer {token}"}, subject


def sign_in(people: People, email: str, *, signed_in_ago: int = 60) -> dict[str, str]:
    return sign_in_as(people, email, signed_in_ago=signed_in_ago)[0]


def user_exists(owner_engine: Engine, subject: str) -> bool:
    with owner_engine.connect() as conn:
        found = conn.execute(
            text("SELECT count(*) FROM users WHERE auth_subject = :s"), {"s": subject}
        )
        return bool(found.scalar_one())


@pytest.mark.parametrize("path", PAGES)
def test_everyone_else_gets_not_found(admins: People, owner_engine: Engine, path: str) -> None:
    unknown = admins.client.get("/v1/admin/nothing-here", headers=sign_in(admins, "x@example.com"))
    someone, subject = sign_in_as(admins, "casey@example.com")
    response = admins.client.get(path, headers=someone)
    # Exactly what a path that doesn't exist looks like.
    assert response.status_code == 404
    assert response.json() == unknown.json() == {"detail": "Not Found"}
    # Turned away before the database: not even signed up.
    assert not user_exists(owner_engine, subject)


@pytest.mark.parametrize("path", PAGES)
def test_signed_out_is_401(admins: People, path: str) -> None:
    assert admins.client.get(path).status_code == 401


def test_nobody_is_an_admin_by_default(people: People) -> None:
    response = people.client.get(PAGES[0], headers=sign_in(people, ADMIN.lower()))
    assert response.status_code == 404


def test_an_admin_must_have_signed_in_recently(admins: People) -> None:
    stale = sign_in(admins, ADMIN.lower(), signed_in_ago=RECENT_SIGN_IN + 60)
    response = admins.client.get(PAGES[0], headers=stale)
    assert response.status_code == 403
    assert response.json() == {"detail": "Sign in again to open the admin page."}


def test_the_overview(admins: People, owner_engine: Engine) -> None:
    casey = admins.new("Casey")
    create(admins, casey, "Thursday Smashers")
    boss, subject = sign_in_as(admins, ADMIN.upper())
    response = admins.client.get("/v1/admin/overview", headers=boss)
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


def test_the_groups(admins: People) -> None:
    casey = admins.new("Casey")
    group_id = create(admins, casey, "Thursday Smashers")["id"]
    response = admins.client.get("/v1/admin/groups", headers=sign_in(admins, ADMIN.lower()))
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


def test_the_app_can_record_its_own_views_only(people: People, app_engine: Engine) -> None:
    casey = people.user_id(people.new("Casey"))
    sam = people.user_id(people.new("Sam"))
    insert = "INSERT INTO admin_views (user_id, page) VALUES (:u, 'overview')"
    with as_user(app_engine, casey) as conn:
        assert sqlstate_of(conn, "SELECT count(*) FROM admin_views") == INSUFFICIENT_PRIVILEGE
        assert sqlstate_of(conn, insert, {"u": sam}) == INSUFFICIENT_PRIVILEGE
        assert sqlstate_of(conn, insert, {"u": casey}) is None
