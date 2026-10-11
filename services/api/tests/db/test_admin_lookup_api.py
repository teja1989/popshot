"""Admin lookup (migration 0011, routes/admin_lookup.py): search, a person, a crew."""

from uuid import uuid4

import pytest
from sqlalchemy import Engine, text

from tests.db.conftest import ADMIN, People, create, sign_in, sign_in_as
from tests.fakes import FakeAccountLookup

pytestmark = pytest.mark.db


@pytest.fixture
def accounts(admins: People) -> FakeAccountLookup:
    fake = FakeAccountLookup()
    admins.client.app.state.account_lookup = fake  # type: ignore[attr-defined]
    return fake


def boss(people: People) -> dict[str, str]:
    return sign_in(people, ADMIN.lower())


@pytest.mark.parametrize(
    "path",
    ["/v1/admin/people?q=casey", f"/v1/admin/people/{uuid4()}", f"/v1/admin/groups/{uuid4()}"],
)
def test_everyone_else_gets_not_found(admins: People, path: str) -> None:
    response = admins.client.get(path, headers=admins.new("Casey"))
    assert (response.status_code, response.json()) == (404, {"detail": "Not Found"})


def test_search_by_name_id_and_email(admins: People, accounts: FakeAccountLookup) -> None:
    casey, subject = sign_in_as(admins, "casey@example.com")
    accounts.add(subject, "casey@example.com")
    casey_id = admins.user_id(casey)
    tag = uuid4().hex[:8]
    admins.client.patch("/v1/me", json={"display_name": f"Casey {tag}"}, headers=casey)

    def search(q: str) -> list[str]:
        response = admins.client.get("/v1/admin/people", params={"q": q}, headers=boss(admins))
        assert response.status_code == 200, response.text
        return [p["id"] for p in response.json()["people"]]

    assert str(casey_id) in search(tag.upper())  # any part of the name, any case
    assert search(str(casey_id)) == [str(casey_id)]
    assert search("Casey@Example.com") == [str(casey_id)]
    assert search("nobody@example.com") == []
    # LIKE wildcards are just characters.
    assert str(casey_id) not in search("%_")


def test_email_search_says_when_firebase_cant_be_asked(admins: People) -> None:
    # No fake set up: lookup is off, as it is locally.
    response = admins.client.get(
        "/v1/admin/people", params={"q": "casey@example.com"}, headers=boss(admins)
    )
    assert response.json() == {"people": [], "email_search": False}


def test_search_needs_two_characters(admins: People) -> None:
    response = admins.client.get("/v1/admin/people", params={"q": "c"}, headers=boss(admins))
    assert response.status_code == 422


def test_a_person(admins: People, accounts: FakeAccountLookup, owner_engine: Engine) -> None:
    casey, subject = sign_in_as(admins, "casey@example.com")
    accounts.add(subject, "casey@example.com")
    casey_id = admins.user_id(casey)
    group = create(admins, casey, "Thursday Smashers")
    admin_headers, admin_subject = sign_in_as(admins, ADMIN.lower())
    response = admins.client.get(f"/v1/admin/people/{casey_id}", headers=admin_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["email"], body["account"], body["disabled"]) == (
        "casey@example.com",
        "found",
        False,
    )
    assert "auth_subject" not in body
    assert body["last_active"] is not None
    assert [(g["group_id"], g["name"], g["role"], g["status"]) for g in body["groups"]] == [
        (group["id"], "Thursday Smashers", "lead", "active")
    ]
    # Recorded with who was opened.
    with owner_engine.connect() as conn:
        target = conn.execute(
            text(
                "SELECT v.target_id FROM admin_views v JOIN users u ON u.id = v.user_id "
                "WHERE u.auth_subject = :s AND v.page = 'person'"
            ),
            {"s": admin_subject},
        ).scalar_one()
    assert target == casey_id


def test_a_person_when_firebase_cant_be_asked(admins: People) -> None:
    casey_id = admins.user_id(admins.new("Casey"))
    body = admins.client.get(f"/v1/admin/people/{casey_id}", headers=boss(admins)).json()
    assert (body["email"], body["account"]) == (None, "unavailable")


def test_a_crew(admins: People) -> None:
    casey = admins.new("Casey")
    group = create(admins, casey, "Thursday Smashers")
    response = admins.client.get(f"/v1/admin/groups/{group['id']}", headers=boss(admins))
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["name"], body["members"], body["games"], body["deleted_at"]) == (
        "Thursday Smashers",
        1,
        0,
        None,
    )
    assert [(p["display_name"], p["role"], p["status"]) for p in body["people"]] == [
        ("Casey", "lead", "active")
    ]


@pytest.mark.parametrize(("kind", "what"), [("people", "person"), ("groups", "crew")])
def test_unknown_ids(admins: People, kind: str, what: str) -> None:
    response = admins.client.get(f"/v1/admin/{kind}/{uuid4()}", headers=boss(admins))
    assert (response.status_code, response.json()) == (404, {"detail": f"No such {what}."})
