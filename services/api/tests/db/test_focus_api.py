"""Private focus areas and post-game reflections, against the real database."""

from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import Engine, text

from popshot_api.focus import (
    FOCUS_OPTIONS,
    MAX_IMPROVE,
    MAX_PER_REFLECTION,
    MAX_STRENGTHS,
    SUGGEST_MIN,
)
from tests.db.conftest import (
    INSUFFICIENT_PRIVILEGE,
    People,
    as_user,
    committed_as,
    create,
    sqlstate_of,
)
from tests.db.test_games_api import join_and_approve, log, players

pytestmark = pytest.mark.db

Headers = dict[str, str]


@pytest.fixture
def pair(people: People) -> dict[str, Any]:
    """Casey (lead) and Sam in one group, plus a guest Gary. Sam and Casey play singles."""
    casey = people.new("Casey")
    group_id = create(people, casey)["id"]
    sam = join_and_approve(people, casey, group_id, "Sam")
    people.client.post(
        f"/v1/groups/{group_id}/players", json={"display_name": "Gary"}, headers=casey
    )
    ids = {name: p["id"] for name, p in players(people, casey, group_id).items()}
    return {"group_id": group_id, "casey": casey, "sam": sam, "ids": ids}


def singles(people: People, headers: Headers, pair: dict[str, Any], a: str, b: str) -> str:
    response = log(
        people,
        headers,
        pair["group_id"],
        format="singles",
        team_a=[pair["ids"][a]],
        team_b=[pair["ids"][b]],
    )
    assert response.status_code == 201, response.text
    match_id: str = response.json()["id"]
    return match_id


def reflect(
    people: People,
    headers: Headers,
    game: tuple[str, str],
    went_well: list[str],
    to_improve: list[str],
) -> Any:
    group_id, match_id = game
    return people.client.put(
        f"/v1/groups/{group_id}/matches/{match_id}/reflection",
        json={"went_well": went_well, "to_improve": to_improve},
        headers=headers,
    )


def focus(people: People, headers: Headers) -> dict[str, Any]:
    response = people.client.get("/v1/me/focus", headers=headers)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def put_focus(people: People, headers: Headers, strengths: list[str], improve: list[str]) -> Any:
    return people.client.put(
        "/v1/me/focus", json={"strengths": strengths, "improve": improve}, headers=headers
    )


def test_options_are_offered_in_order(people: People) -> None:
    listed = people.client.get("/v1/focus-options", headers=people.new("Casey")).json()
    assert [o["id"] for o in listed] == [o.id for o in FOCUS_OPTIONS if not o.retired]
    assert len(listed) >= 20
    assert len({o["id"] for o in listed}) == len(listed)
    assert listed[0] == {
        "id": "serve_consistency",
        "label": "Serve consistency",
        "area": "Serve & return",
    }


def test_profile_focus_starts_empty_and_saves(people: People) -> None:
    casey = people.new("Casey")
    assert focus(people, casey) == {"strengths": [], "improve": [], "suggestions": []}
    response = put_focus(people, casey, ["footwork", "third_shot_drop"], ["serve_consistency"])
    assert response.status_code == 200
    assert response.json()["strengths"] == ["footwork", "third_shot_drop"]
    assert focus(people, casey)["improve"] == ["serve_consistency"]
    # Saving again replaces, it doesn't add.
    put_focus(people, casey, [], ["footwork"])
    assert (focus(people, casey)["strengths"], focus(people, casey)["improve"]) == (
        [],
        ["footwork"],
    )


@pytest.mark.parametrize(
    ("strengths", "improve"),
    [
        (["footwork"], ["footwork"]),
        (["footwork", "footwork"], []),
        (["not_a_thing"], []),
        (["Footwork"], []),
        ([o.id for o in FOCUS_OPTIONS[: MAX_STRENGTHS + 1]], []),
        ([], [o.id for o in FOCUS_OPTIONS[: MAX_IMPROVE + 1]]),
    ],
)
def test_bad_profile_focus_is_rejected(
    people: People, strengths: list[str], improve: list[str]
) -> None:
    casey = people.new("Casey")
    assert put_focus(people, casey, strengths, improve).status_code == 422
    assert focus(people, casey)["strengths"] == []
    extra = people.client.put(
        "/v1/me/focus",
        json={"strengths": [], "improve": [], "user_id": str(uuid4())},
        headers=casey,
    )
    assert extra.status_code == 422


def test_profile_focus_is_private_even_in_the_database(
    people: People, pair: dict[str, Any], app_engine: Engine
) -> None:
    put_focus(people, pair["casey"], ["footwork"], ["serve_consistency"])
    casey_id, sam_id = people.user_id(pair["casey"]), people.user_id(pair["sam"])
    # Sam shares a group with Casey and still can't read, write or overwrite Casey's focus.
    assert focus(people, pair["sam"])["strengths"] == []
    with as_user(app_engine, sam_id) as conn:
        seen = conn.execute(
            text("SELECT count(*) FROM user_focus WHERE user_id = :u"), {"u": casey_id}
        ).scalar_one()
        assert seen == 0
        changed = conn.execute(
            text("UPDATE user_focus SET strengths = '{}' WHERE user_id = :u"), {"u": casey_id}
        ).rowcount
        assert changed == 0
        state = sqlstate_of(
            conn,
            "INSERT INTO user_focus (user_id, strengths) VALUES (:u, '{}')",
            {"u": casey_id},
        )
        assert state == INSUFFICIENT_PRIVILEGE
        # Nor can anyone move a row to another user.
        state = sqlstate_of(
            conn,
            "UPDATE user_focus SET user_id = :u WHERE user_id = :me",
            {"u": casey_id, "me": sam_id},
        )
        assert state == INSUFFICIENT_PRIVILEGE
    assert focus(people, pair["casey"])["strengths"] == ["footwork"]


def test_database_rejects_bad_ids_and_overlap(people: People, app_engine: Engine) -> None:
    casey = people.new("Casey")
    casey_id = people.user_id(casey)
    with as_user(app_engine, casey_id) as conn:
        for strengths, improve in (
            ("{Bad Id}", "{}"),
            ("{footwork,footwork}", "{}"),
            ("{footwork}", "{footwork}"),
            ("{a,b,c,d,e,f,g}", "{}"),
        ):
            state = sqlstate_of(
                conn,
                "INSERT INTO user_focus (user_id, strengths, improve) VALUES (:u, :s, :i)",
                {"u": casey_id, "s": strengths, "i": improve},
            )
            assert state == "23514", (strengths, improve)  # check_violation


def test_players_reflect_on_their_own_game(people: People, pair: dict[str, Any]) -> None:
    group_id = pair["group_id"]
    match_id = singles(people, pair["casey"], pair, "Casey", "Sam")
    saved = reflect(people, pair["sam"], (group_id, match_id), ["footwork"], ["serve_consistency"])
    assert saved.status_code == 200, saved.text
    # Changing your mind replaces the reflection.
    reflect(people, pair["sam"], (group_id, match_id), ["return_of_serve"], [])

    def mine(headers: Headers) -> dict[str, Any]:
        listed = people.client.get(f"/v1/groups/{group_id}/matches", headers=headers).json()
        game: dict[str, Any] = next(m for m in listed if m["id"] == match_id)
        return game

    as_sam = mine(pair["sam"])
    assert as_sam["i_played"] is True
    assert as_sam["my_reflection"] == {"went_well": ["return_of_serve"], "to_improve": []}
    # Casey played too but hasn't reflected, and never sees Sam's.
    as_casey = mine(pair["casey"])
    assert (as_casey["i_played"], as_casey["my_reflection"]) == (True, None)

    # Skipping records an empty reflection, so the prompt stops.
    assert reflect(people, pair["casey"], (group_id, match_id), [], []).status_code == 200
    assert mine(pair["casey"])["my_reflection"] == {"went_well": [], "to_improve": []}


def test_reflections_are_private_within_the_group(
    people: People, pair: dict[str, Any], app_engine: Engine
) -> None:
    match_id = singles(people, pair["casey"], pair, "Casey", "Sam")
    reflect(people, pair["sam"], (pair["group_id"], match_id), ["footwork"], [])
    with as_user(app_engine, people.user_id(pair["casey"])) as conn:
        seen = conn.execute(
            text("SELECT count(*) FROM match_reflections WHERE match_id = :m"), {"m": match_id}
        ).scalar_one()
        assert seen == 0
        changed = conn.execute(
            text("UPDATE match_reflections SET went_well = '{}' WHERE match_id = :m"),
            {"m": match_id},
        ).rowcount
        assert changed == 0


def test_who_can_reflect(people: People, pair: dict[str, Any], app_engine: Engine) -> None:
    group_id = pair["group_id"]
    # Sam logs a game between Casey and the guest; Sam didn't play.
    match_id = singles(people, pair["sam"], pair, "Casey", "Gary")
    response = reflect(people, pair["sam"], (group_id, match_id), ["footwork"], [])
    assert response.status_code == 403
    outsider = people.new("Jordan")
    assert reflect(people, outsider, (group_id, match_id), ["footwork"], []).status_code == 404
    assert reflect(people, pair["casey"], (group_id, str(uuid4())), [], []).status_code == 404
    other_group = create(people, outsider)["id"]
    assert reflect(people, pair["casey"], (other_group, match_id), [], []).status_code == 404

    # Removed from the group: no more reflecting there.
    sam_game = singles(people, pair["casey"], pair, "Casey", "Sam")
    people.client.patch(
        f"/v1/groups/{group_id}/members/{people.user_id(pair['sam'])}",
        json={"action": "remove"},
        headers=pair["casey"],
    )
    assert reflect(people, pair["sam"], (group_id, sam_game), ["footwork"], []).status_code == 404

    # Too long ago.
    with committed_as(app_engine, people.user_id(pair["casey"])) as conn:
        conn.execute(
            text("UPDATE matches SET played_at = now() - interval '31 days' WHERE id = :m"),
            {"m": match_id},
        )
    assert reflect(people, pair["casey"], (group_id, match_id), [], []).status_code == 409


@pytest.mark.parametrize(
    ("went_well", "to_improve"),
    [
        (["footwork"], ["footwork"]),
        ([o.id for o in FOCUS_OPTIONS[: MAX_PER_REFLECTION + 1]], []),
        (["nope"], []),
        (["footwork", "footwork"], []),
    ],
)
def test_bad_reflections_are_rejected(
    people: People, pair: dict[str, Any], went_well: list[str], to_improve: list[str]
) -> None:
    match_id = singles(people, pair["casey"], pair, "Casey", "Sam")
    response = reflect(people, pair["casey"], (pair["group_id"], match_id), went_well, to_improve)
    assert response.status_code == 422


def test_suggestions_come_from_repeated_reflections(people: People, pair: dict[str, Any]) -> None:
    group_id, casey = pair["group_id"], pair["casey"]
    games = [singles(people, casey, pair, "Casey", "Gary") for _ in range(SUGGEST_MIN + 1)]
    # Third-shot drops went well in SUGGEST_MIN - 1 games: not enough yet.
    for match_id in games[: SUGGEST_MIN - 1]:
        reflect(people, casey, (group_id, match_id), ["third_shot_drop"], ["serve_consistency"])
    # A skipped game doesn't count either way.
    reflect(people, casey, (group_id, games[SUGGEST_MIN - 1]), [], [])
    assert focus(people, casey)["suggestions"] == []

    reflect(
        people, casey, (group_id, games[SUGGEST_MIN]), ["third_shot_drop"], ["serve_consistency"]
    )
    suggestions = focus(people, casey)["suggestions"]
    assert suggestions == [
        {
            "option_id": "third_shot_drop",
            "kind": "strength",
            "count": SUGGEST_MIN,
            "out_of": SUGGEST_MIN,
        },
        {
            "option_id": "serve_consistency",
            "kind": "improve",
            "count": SUGGEST_MIN,
            "out_of": SUGGEST_MIN,
        },
    ]

    # Promoting one (the client saves the new lists) removes its suggestion.
    put_focus(people, casey, ["third_shot_drop"], [])
    assert [s["option_id"] for s in focus(people, casey)["suggestions"]] == ["serve_consistency"]
    # Someone else's reflections never feed your suggestions.
    assert focus(people, pair["sam"])["suggestions"] == []


def test_deleting_a_game_removes_its_reflections(people: People, pair: dict[str, Any]) -> None:
    group_id = pair["group_id"]
    match_id = singles(people, pair["casey"], pair, "Casey", "Sam")
    reflect(people, pair["sam"], (group_id, match_id), ["footwork"], [])
    deleted = people.client.delete(
        f"/v1/groups/{group_id}/matches/{match_id}", headers=pair["casey"]
    )
    assert deleted.status_code == 204
    assert reflect(people, pair["sam"], (group_id, match_id), [], []).status_code == 404
