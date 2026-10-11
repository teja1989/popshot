"""Players, guests, logging games and editing your name, against the real database."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import Engine, text

from popshot_api.routes.games import MAX_GUESTS
from tests.db.conftest import People, as_user, committed_as, create

pytestmark = pytest.mark.db

Headers = dict[str, str]


def join_and_approve(people: People, lead: Headers, group_id: str, name: str) -> Headers:
    member = people.new(name)
    token = people.client.post(f"/v1/groups/{group_id}/invites", json={}, headers=lead).json()[
        "token"
    ]
    assert people.client.post("/v1/invites/join", json={"token": token}, headers=member).is_success
    approved = people.client.patch(
        f"/v1/groups/{group_id}/members/{people.user_id(member)}",
        json={"action": "approve"},
        headers=lead,
    )
    assert approved.status_code == 200, approved.text
    return member


def players(people: People, headers: Headers, group_id: str) -> dict[str, dict[str, Any]]:
    response = people.client.get(f"/v1/groups/{group_id}/players", headers=headers)
    assert response.status_code == 200, response.text
    return {p["display_name"]: p for p in response.json()}


def add_guest(people: People, headers: Headers, group_id: str, name: str) -> Any:
    return people.client.post(
        f"/v1/groups/{group_id}/players", json={"display_name": name}, headers=headers
    )


def log(people: People, headers: Headers, group_id: str, **overrides: Any) -> Any:
    body: dict[str, Any] = {
        "format": "doubles",
        "points_to": 11,
        "win_by_two": True,
        "best_of": 1,
        "games": [{"team_a": 11, "team_b": 7}],
    }
    body.update(overrides)
    return people.client.post(f"/v1/groups/{group_id}/matches", json=body, headers=headers)


@pytest.fixture
def crew(people: People) -> dict[str, Any]:
    """Casey (lead) and Sam, plus guests Gary and Jo. Returns headers and player IDs."""
    casey = people.new("Casey")
    group_id = create(people, casey)["id"]
    sam = join_and_approve(people, casey, group_id, "Sam")
    for name in ("Gary", "Jo"):
        assert add_guest(people, casey, group_id, name).status_code == 201
    ids = {name: p["id"] for name, p in players(people, casey, group_id).items()}
    return {"group_id": group_id, "casey": casey, "sam": sam, "ids": ids}


def test_players_lists_you_first_then_members_then_guests(
    people: People, crew: dict[str, Any]
) -> None:
    listed = people.client.get(f"/v1/groups/{crew['group_id']}/players", headers=crew["sam"]).json()
    assert [(p["display_name"], p["is_me"], p["is_guest"]) for p in listed] == [
        ("Sam", True, False),
        ("Casey", False, False),
        ("Gary", False, True),
        ("Jo", False, True),
    ]


def test_guest_names_are_checked(people: People, crew: dict[str, Any]) -> None:
    group_id, sam = crew["group_id"], crew["sam"]
    clash = add_guest(people, sam, group_id, "  gary ")
    assert clash.status_code == 409
    assert "already a player called gary" in clash.json()["detail"]
    # A member's name counts too.
    assert add_guest(people, sam, group_id, "CASEY").status_code == 409
    for bad in ("", "   ", "x" * 41, "Bad\u202ename"):
        assert add_guest(people, sam, group_id, bad).status_code == 422
    made = add_guest(people, sam, group_id, " Robin ")
    assert made.status_code == 201
    assert made.json()["display_name"] == "Robin"
    assert made.json()["is_guest"] is True


def test_guest_cap(people: People, app_engine: Engine) -> None:
    casey = people.new("Casey")
    group_id = create(people, casey)["id"]
    with committed_as(app_engine, people.user_id(casey)) as conn:
        conn.execute(
            text(
                "INSERT INTO players (group_id, display_name) "
                "SELECT :g, 'Guest ' || n FROM generate_series(1, :n) n"
            ),
            {"g": group_id, "n": MAX_GUESTS},
        )
    response = add_guest(people, casey, group_id, "One more")
    assert response.status_code == 409
    assert f"up to {MAX_GUESTS} guests" in response.json()["detail"]


def test_outsiders_and_pending_people_see_nothing(people: People, crew: dict[str, Any]) -> None:
    group_id = crew["group_id"]
    outsider = people.new("Jordan")
    pending = people.new("Riley")
    token = people.client.post(
        f"/v1/groups/{group_id}/invites", json={}, headers=crew["casey"]
    ).json()["token"]
    people.client.post("/v1/invites/join", json={"token": token}, headers=pending)
    a, b = crew["ids"]["Casey"], crew["ids"]["Sam"]
    for headers in (outsider, pending):
        assert (
            people.client.get(f"/v1/groups/{group_id}/players", headers=headers).status_code == 404
        )
        assert add_guest(people, headers, group_id, "Sneaky").status_code == 404
        assert (
            people.client.get(f"/v1/groups/{group_id}/matches", headers=headers).status_code == 404
        )
        response = log(people, headers, group_id, format="singles", team_a=[a], team_b=[b])
        assert response.status_code == 404


def test_log_a_doubles_game_with_guests(people: People, crew: dict[str, Any]) -> None:
    group_id, ids = crew["group_id"], crew["ids"]
    response = log(
        people,
        crew["sam"],
        group_id,
        team_a=[ids["Sam"], ids["Gary"]],
        team_b=[ids["Casey"], ids["Jo"]],
        games=[{"team_a": 9, "team_b": 11}],
    )
    assert response.status_code == 201, response.text
    match = response.json()
    assert (match["status"], match["winner"], match["entered_by_me"]) == ("pending", "B", True)
    assert match["entered_by_name"] == "Sam"
    assert {(p["display_name"], p["team"], p["is_guest"]) for p in match["players"]} == {
        ("Sam", "A", False),
        ("Gary", "A", True),
        ("Casey", "B", False),
        ("Jo", "B", True),
    }
    assert match["games"] == [{"team_a": 9, "team_b": 11}]
    played = datetime.fromisoformat(match["played_at"])
    assert abs(played - datetime.now(UTC)) < timedelta(minutes=1)

    # Everyone in the group sees it; Casey didn't log it.
    listed = people.client.get(f"/v1/groups/{group_id}/matches", headers=crew["casey"]).json()
    assert [(m["id"], m["entered_by_me"]) for m in listed] == [(match["id"], False)]


def test_a_member_can_log_a_game_they_didnt_play(people: People, crew: dict[str, Any]) -> None:
    ids = crew["ids"]
    response = log(
        people,
        crew["sam"],
        crew["group_id"],
        format="singles",
        team_a=[ids["Gary"]],
        team_b=[ids["Jo"]],
        best_of=3,
        games=[
            {"team_a": 11, "team_b": 4},
            {"team_a": 7, "team_b": 11},
            {"team_a": 13, "team_b": 11},
        ],
    )
    assert response.status_code == 201, response.text
    assert response.json()["winner"] == "A"


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"games": [{"team_a": 11, "team_b": 10}]}, "two points ahead"),
        ({"best_of": 3}, "isn't finished"),
        ({"format": "singles"}, "one player on each side"),
        ({"team_b": ["Sam", "Jo"]}, "only be in a game once"),
        ({"team_b": ["Casey"]}, "two players on each team"),
        ({"played_at": "2026-01-01T10:00:00"}, "time zone"),
    ],
)
def test_bad_games_are_rejected_with_a_reason(
    people: People, crew: dict[str, Any], overrides: dict[str, Any], message: str
) -> None:
    ids = crew["ids"]
    body: dict[str, Any] = {
        "team_a": [ids["Sam"], ids["Gary"]],
        "team_b": [ids["Casey"], ids["Jo"]],
    }
    for team in ("team_a", "team_b"):
        if team in overrides:
            overrides[team] = [ids[n] for n in overrides[team]]
    body.update(overrides)
    response = log(people, crew["sam"], crew["group_id"], **body)
    assert response.status_code == 422
    assert message in response.json()["detail"]
    assert (
        people.client.get(f"/v1/groups/{crew['group_id']}/matches", headers=crew["sam"]).json()
        == []
    )


def test_played_at_must_be_recent_and_not_in_the_future(
    people: People, crew: dict[str, Any]
) -> None:
    ids = crew["ids"]
    teams = {"format": "singles", "team_a": [ids["Sam"]], "team_b": [ids["Casey"]]}
    now = datetime.now(UTC)
    for when, ok in (
        (now - timedelta(days=2), True),
        (now + timedelta(hours=1), False),
        (now - timedelta(days=31), False),
    ):
        response = log(people, crew["sam"], crew["group_id"], played_at=when.isoformat(), **teams)
        assert (response.status_code == 201) is ok, response.text


def test_cannot_use_players_from_another_group_or_removed_members(
    people: People, crew: dict[str, Any]
) -> None:
    group_id, casey, ids = crew["group_id"], crew["casey"], crew["ids"]
    other = people.new("Jordan")
    other_group = create(people, other)["id"]
    stranger = players(people, other, other_group)["Jordan"]["id"]
    response = log(
        people, casey, group_id, format="singles", team_a=[ids["Casey"]], team_b=[stranger]
    )
    assert response.status_code == 422
    assert "aren't in this group" in response.json()["detail"]
    assert (
        log(
            people, casey, group_id, format="singles", team_a=[ids["Casey"]], team_b=[str(uuid4())]
        ).status_code
        == 422
    )

    sam_id = people.user_id(crew["sam"])
    removed = people.client.patch(
        f"/v1/groups/{group_id}/members/{sam_id}", json={"action": "remove"}, headers=casey
    )
    assert removed.status_code == 200
    assert "Sam" not in players(people, casey, group_id)
    response = log(
        people, casey, group_id, format="singles", team_a=[ids["Casey"]], team_b=[ids["Sam"]]
    )
    assert response.status_code == 422


def test_rejects_non_integer_scores(people: People, crew: dict[str, Any]) -> None:
    ids = crew["ids"]
    for games in (
        [{"team_a": "11", "team_b": 7}],
        [{"team_a": 11.0, "team_b": 7}],
        [{"team_a": True, "team_b": 7}],
    ):
        response = log(
            people,
            crew["sam"],
            crew["group_id"],
            format="singles",
            team_a=[ids["Sam"]],
            team_b=[ids["Casey"]],
            games=games,
        )
        assert response.status_code == 422


def test_only_the_logger_deletes_and_only_while_pending(
    people: People, crew: dict[str, Any], app_engine: Engine
) -> None:
    group_id, ids = crew["group_id"], crew["ids"]
    teams = {"format": "singles", "team_a": [ids["Sam"]], "team_b": [ids["Casey"]]}
    first = log(people, crew["sam"], group_id, **teams).json()["id"]
    second = log(people, crew["sam"], group_id, **teams).json()["id"]
    path = f"/v1/groups/{group_id}/matches"

    assert people.client.delete(f"{path}/{first}", headers=crew["casey"]).status_code == 403
    assert people.client.delete(f"{path}/{uuid4()}", headers=crew["sam"]).status_code == 404
    assert people.client.delete(f"{path}/{first}", headers=crew["sam"]).status_code == 204
    assert [m["id"] for m in people.client.get(path, headers=crew["sam"]).json()] == [second]

    # Once someone has confirmed, it stays.
    casey_id = people.user_id(crew["casey"])
    with committed_as(app_engine, casey_id) as conn:
        conn.execute(
            text(
                "INSERT INTO match_confirmations (match_id, group_id, user_id, decision) "
                "VALUES (:m, :g, :u, 'confirm')"
            ),
            {"m": second, "g": group_id, "u": casey_id},
        )
    assert people.client.delete(f"{path}/{second}", headers=crew["sam"]).status_code == 409

    # Another group's game is a 404, not a 403.
    other = people.new("Jordan")
    other_group = create(people, other)["id"]
    assert (
        people.client.delete(
            f"/v1/groups/{other_group}/matches/{second}", headers=other
        ).status_code
        == 404
    )


def test_logging_writes_the_audit_log(
    people: People, crew: dict[str, Any], app_engine: Engine
) -> None:
    ids = crew["ids"]
    match_id = log(
        people,
        crew["sam"],
        crew["group_id"],
        format="singles",
        team_a=[ids["Sam"]],
        team_b=[ids["Gary"]],
    ).json()["id"]
    with as_user(app_engine, people.user_id(crew["casey"])) as conn:
        rows = conn.execute(
            text(
                "SELECT action, actor_user_id FROM audit_log WHERE group_id = :g AND target_id = :m"
            ),
            {"g": crew["group_id"], "m": match_id},
        ).all()
    assert [(r.action, r.actor_user_id) for r in rows] == [
        ("match.logged", people.user_id(crew["sam"]))
    ]


def test_edit_your_name(people: People, crew: dict[str, Any]) -> None:
    group_id, sam = crew["group_id"], crew["sam"]
    response = people.client.patch("/v1/me", json={"display_name": "  Sammy  "}, headers=sam)
    assert response.status_code == 200
    assert response.json()["display_name"] == "Sammy"
    assert people.client.get("/v1/me", headers=sam).json()["display_name"] == "Sammy"
    # The name shows in the group and on your player.
    assert "Sammy" in players(people, crew["casey"], group_id)
    detail = people.client.get(f"/v1/groups/{group_id}", headers=crew["casey"]).json()
    assert "Sammy" in [m["display_name"] for m in detail["members"]]
    # Signing in again doesn't put the Google name back.
    assert people.client.get("/v1/me", headers=sam).json()["display_name"] == "Sammy"

    for bad in ("", "   ", "x" * 41, "Zero\u200bwidth"):
        assert (
            people.client.patch("/v1/me", json={"display_name": bad}, headers=sam).status_code
            == 422
        )
    assert (
        people.client.patch(
            "/v1/me", json={"display_name": "Ok", "avatar_url": "https://evil"}, headers=sam
        ).status_code
        == 422
    )


def test_editing_your_name_only_touches_your_rows(people: People, crew: dict[str, Any]) -> None:
    people.client.patch("/v1/me", json={"display_name": "Sammy"}, headers=crew["sam"])
    names = set(players(people, crew["casey"], crew["group_id"]))
    assert names == {"Casey", "Sammy", "Gary", "Jo"}
