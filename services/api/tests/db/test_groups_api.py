"""The groups endpoints end to end against the real database, with fake tokens."""

import secrets
from collections.abc import Iterator
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from popshot_api.auth.verifier import VerifiedIdentity
from popshot_api.main import create_app
from popshot_api.routes.groups import MAX_LED_GROUPS, MEMBER_PREVIEW
from tests.conftest import make_settings
from tests.db.conftest import _create_invite, _redeem, committed_as
from tests.fakes import FakeTokenVerifier

pytestmark = pytest.mark.db


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


def test_create_makes_you_the_lead(people: People) -> None:
    maya = people.new("Maya")
    response = people.client.post(
        "/v1/groups",
        json={"name": "  Tuesday Dinkers  ", "default_points_to": 15, "default_win_by_two": False},
        headers=maya,
    )
    assert response.status_code == 201
    group = response.json()
    assert group["name"] == "Tuesday Dinkers"
    assert group["my_role"] == "lead"
    assert group["my_status"] == "active"
    assert group["member_count"] == 1
    assert (group["default_format"], group["default_points_to"], group["default_win_by_two"]) == (
        "doubles",
        15,
        False,
    )
    assert [(m["display_name"], m["role"], m["status"]) for m in group["members"]] == [
        ("Maya", "lead", "active")
    ]


def test_list_shows_only_your_groups(people: People) -> None:
    maya, sam = people.new("Maya"), people.new("Sam")
    mine = create(people, maya, "Zeta Crew")
    create(people, maya, "alpha crew")
    create(people, sam, "Sam's Crew")

    listed = people.client.get("/v1/groups", headers=maya).json()
    assert [g["name"] for g in listed] == ["alpha crew", "Zeta Crew"]
    assert all(g["my_role"] == "lead" and g["member_count"] == 1 for g in listed)
    assert mine["id"] in {g["id"] for g in listed}


def test_someone_elses_group_is_not_found(people: People) -> None:
    maya, sam = people.new("Maya"), people.new("Sam")
    group = create(people, maya)
    for path in (f"/v1/groups/{group['id']}", f"/v1/groups/{uuid4()}"):
        response = people.client.get(path, headers=sam)
        assert response.status_code == 404
        assert response.json() == {"detail": "We couldn't find that group."}
    assert people.client.get("/v1/groups/not-a-uuid", headers=sam).status_code == 422


def test_requires_sign_in(people: People) -> None:
    assert people.client.get("/v1/groups").status_code == 401
    assert people.client.post("/v1/groups", json={"name": "x"}).status_code == 401
    assert people.client.get(f"/v1/groups/{uuid4()}").status_code == 401


@pytest.mark.parametrize(
    "body",
    [
        {"name": ""},
        {"name": "   "},
        {"name": "x" * 61},
        {"name": "bad\u0000name"},
        {"name": "line\nbreak"},
        {"name": "flip" + chr(0x202E) + "emanor"},  # right-to-left override, a spoofing trick
        {"name": "ok", "default_points_to": 12},
        {"name": "ok", "default_format": "triples"},
        {"name": "ok", "default_win_by_two": "maybe"},
        {"name": "ok", "id": str(uuid4())},
        {"name": "ok", "created_by": str(uuid4())},
        {},
    ],
)
def test_rejects_bad_input(people: People, body: dict[str, Any]) -> None:
    maya = people.new("Maya")
    response = people.client.post("/v1/groups", json=body, headers=maya)
    assert response.status_code == 422
    assert people.client.get("/v1/groups", headers=maya).json() == []


@pytest.mark.parametrize("name", ["x" * 60, "Café Pickleball ñ 🏓", "O'Brien & Co. (Tue/Thu)"])
def test_accepts_real_names(people: People, name: str) -> None:
    assert create(people, people.new("Maya"), name)["name"] == name


def test_caps_how_many_groups_one_person_leads(people: People) -> None:
    maya = people.new("Maya")
    for n in range(MAX_LED_GROUPS):
        create(people, maya, f"Crew {n}")
    response = people.client.post("/v1/groups", json={"name": "One too many"}, headers=maya)
    assert response.status_code == 409
    assert len(people.client.get("/v1/groups", headers=maya).json()) == MAX_LED_GROUPS
    # Someone else is unaffected.
    create(people, people.new("Sam"), "Sam's Crew")


def test_pending_and_member_views(people: People, app_engine: Engine) -> None:
    maya, sam, priya = people.new("Maya"), people.new("Sam"), people.new("Priya")
    group = create(people, maya)
    group_id = UUID(group["id"])
    maya_id = people.user_id(maya)

    # Sam joins straight away; Priya has to wait for approval.
    with committed_as(app_engine, maya_id) as conn:
        _, open_invite = _create_invite(conn, group_id, maya_id, approval=False)
        _, approval_invite = _create_invite(conn, group_id, maya_id, approval=True)
    _redeem(app_engine, people.user_id(sam), open_invite)
    _redeem(app_engine, people.user_id(priya), approval_invite)

    # Priya, waiting: sees the group exists for her, but not who is in it.
    waiting = people.client.get(f"/v1/groups/{group_id}", headers=priya).json()
    assert (waiting["my_status"], waiting["member_count"], waiting["members"]) == (
        "pending",
        None,
        [],
    )
    listed = people.client.get("/v1/groups", headers=priya).json()
    assert [(g["my_status"], g["member_count"], g["member_preview"]) for g in listed] == [
        ("pending", None, [])
    ]

    # Sam, a member: sees active members only.
    as_sam = people.client.get(f"/v1/groups/{group_id}", headers=sam).json()
    assert as_sam["my_role"] == "member"
    assert [(m["display_name"], m["status"]) for m in as_sam["members"]] == [
        ("Maya", "active"),
        ("Sam", "active"),
    ]
    assert as_sam["member_count"] == 2

    # Maya, the lead: also sees who is waiting, listed after the active members.
    as_maya = people.client.get(f"/v1/groups/{group_id}", headers=maya).json()
    assert [(m["display_name"], m["role"], m["status"]) for m in as_maya["members"]] == [
        ("Maya", "lead", "active"),
        ("Sam", "member", "active"),
        ("Priya", "member", "pending"),
    ]
    assert as_maya["member_count"] == 2

    # The group card's faces: active members only, the lead first.
    card = people.client.get("/v1/groups", headers=sam).json()[0]
    assert card["member_preview"] == [
        {"display_name": "Maya", "avatar_url": None},
        {"display_name": "Sam", "avatar_url": None},
    ]


def test_member_preview_is_capped(people: People, app_engine: Engine) -> None:
    maya = people.new("Maya")
    group_id = UUID(create(people, maya)["id"])
    maya_id = people.user_id(maya)
    with committed_as(app_engine, maya_id) as conn:
        _, invite = _create_invite(conn, group_id, maya_id, approval=False)
    for n in range(MEMBER_PREVIEW + 2):
        _redeem(app_engine, people.user_id(people.new(f"Player{n}")), invite)

    card = people.client.get("/v1/groups", headers=maya).json()[0]
    assert card["member_count"] == MEMBER_PREVIEW + 3
    assert len(card["member_preview"]) == MEMBER_PREVIEW
    assert card["member_preview"][0]["display_name"] == "Maya"
