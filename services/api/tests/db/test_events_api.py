"""Crew events (migration 0028, routes/events.py): Dink Shuffle and Ride the River.

Each test puts its own crew on the switch's list (feature_crews), so no global switch is
changed under other tests.
"""

import threading
from collections.abc import Callable, Iterator
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import Engine, text

from tests.db.conftest import INSUFFICIENT_PRIVILEGE, People, as_user, create, sqlstate_of
from tests.db.test_features import owner
from tests.db.test_games_api import add_guest, join_and_approve, log, players

pytestmark = pytest.mark.db

Headers = dict[str, str]


class Lists:
    """Put crews on a switch's list, and take them off again after the test."""

    def __init__(self, owner_engine: Engine) -> None:
        self.owner_engine = owner_engine
        self.added: list[tuple[str, str]] = []

    def add(self, key: str, group_id: str) -> None:
        with owner(self.owner_engine) as conn:
            conn.execute(
                text("INSERT INTO feature_crews (feature_key, group_id) VALUES (:k, :g)"),
                {"k": key, "g": group_id},
            )
        self.added.append((key, group_id))

    def remove(self, key: str, group_id: str) -> None:
        with owner(self.owner_engine) as conn:
            conn.execute(
                text("DELETE FROM feature_crews WHERE feature_key = :k AND group_id = :g"),
                {"k": key, "g": group_id},
            )

    def cleanup(self) -> None:
        for key, group_id in self.added:
            self.remove(key, group_id)


@pytest.fixture
def lists(owner_engine: Engine) -> Iterator[Lists]:
    made = Lists(owner_engine)
    yield made
    made.cleanup()


@pytest.fixture
def crew(people: People, lists: Lists) -> dict[str, Any]:
    """Casey leads; Sam and Jo are members; six guests make nine players. Dink Shuffle is on."""
    casey = people.new("Casey")
    gid = create(people, casey, "Event Crew")["id"]
    sam = join_and_approve(people, casey, gid, "Sam")
    jo = join_and_approve(people, casey, gid, "Jo")
    for name in ("Ana", "Bo", "Cy", "Di", "Ed", "Flo"):
        assert add_guest(people, casey, gid, name).status_code == 201
    ids = {name.split()[0]: p["id"] for name, p in players(people, casey, gid).items()}
    lists.add("events.shuffle", gid)
    return {"gid": gid, "casey": casey, "sam": sam, "jo": jo, "ids": ids}


def start(people: People, crew: dict[str, Any], **over: Any) -> Any:
    body: dict[str, Any] = {
        "kind": "shuffle",
        "name": "Saturday Shuffle",
        "players": list(crew["ids"].values()),
        "courts": 2,
        **over,
    }
    return people.client.post(f"/v1/groups/{crew['gid']}/events", json=body, headers=crew["casey"])


def url(crew: dict[str, Any], event: dict[str, Any], rest: str = "") -> str:
    return f"/v1/groups/{crew['gid']}/events/{event['id']}{rest}"


def score(  # noqa: PLR0913 - a test helper with defaults
    people: People,
    crew: dict[str, Any],
    event: dict[str, Any],
    court: int,
    who: Headers,
    *,
    games: list[dict[str, int]] | None = None,
    number: int | None = None,
) -> Any:
    n = number if number is not None else event["round_list"][-1]["number"]
    return people.client.put(
        url(crew, event, "/courts"),
        json={"round": n, "court": court, "games": games or [{"team_a": 11, "team_b": 7}]},
        headers=who,
    )


def test_a_lead_starts_a_shuffle_and_round_one_is_made(
    people: People, crew: dict[str, Any]
) -> None:
    made = start(people, crew)
    assert made.status_code == 201, made.text
    event = made.json()
    assert (event["kind"], event["status"], event["vibe"]) == ("shuffle", "live", "social")
    [first] = event["round_list"]
    # Nine players, two courts: eight play, one sits out.
    assert len(first["courts"]) == 2
    assert len(first["sitting_out"]) == 1
    on_court = {p for c in first["courts"] for p in c["team_a"] + c["team_b"]}
    assert len(on_court) == 8
    assert event["can_manage"] is True
    assert event["can_start_round"] is False
    # Social: no table for anyone.
    assert event["standings"] is None
    listed = people.client.get(f"/v1/groups/{crew['gid']}/events", headers=crew["sam"]).json()
    assert [(e["name"], e["rounds"], e["players"]) for e in listed] == [("Saturday Shuffle", 1, 9)]


def test_only_leads_start_events_and_only_with_the_switch_on(
    people: People, crew: dict[str, Any], lists: Lists, app_engine: Engine
) -> None:
    gid = crew["gid"]
    body = {"kind": "shuffle", "name": "Mine", "players": list(crew["ids"].values()), "courts": 2}
    member = people.client.post(f"/v1/groups/{gid}/events", json=body, headers=crew["sam"])
    assert member.status_code == 403
    # Ride the River isn't on for this crew.
    river = start(people, crew, kind="river", seeding="random")
    assert (river.status_code, river.json()["detail"]) == (
        403,
        "Ride the River isn't switched on for this crew yet.",
    )
    # Off the list: refused by the API...
    lists.remove("events.shuffle", gid)
    off = start(people, crew)
    assert (off.status_code, off.json()["detail"]) == (
        403,
        "Dink Shuffle isn't switched on for this crew yet.",
    )
    # ...and by the database, even going around the API.
    casey = people.user_id(crew["casey"])
    with as_user(app_engine, casey) as conn:
        insert = (
            "INSERT INTO events (group_id, kind, name, points_to, win_by_two, best_of, courts, "
            "seed, created_by) VALUES (:g, 'shuffle', 'Sneaky', 11, true, 1, 2, 1, :u)"
        )
        assert sqlstate_of(conn, insert, {"g": gid, "u": casey}) == INSUFFICIENT_PRIVILEGE


def test_a_running_event_carries_on_when_the_switch_goes_off(
    people: People, crew: dict[str, Any], lists: Lists
) -> None:
    event = start(people, crew).json()
    lists.remove("events.shuffle", crew["gid"])
    for c in (1, 2):
        assert score(people, crew, event, c, crew["sam"]).status_code == 200
    second = people.client.post(url(crew, event, "/rounds"), headers=crew["casey"])
    assert second.status_code == 201, second.text
    done = people.client.post(url(crew, event, "/finish"), headers=crew["casey"])
    assert done.json()["status"] == "finished"


def test_scores_become_games_and_only_leads_change_them(
    people: People, crew: dict[str, Any]
) -> None:
    event = start(people, crew).json()
    # Anyone in the crew fills in a court.
    filled = score(people, crew, event, 1, crew["sam"])
    assert filled.status_code == 200, filled.text
    court = filled.json()["round_list"][0]["courts"][0]
    assert court["winner"] == "A"
    assert court["games"] == [{"team_a": 11, "team_b": 7}]
    # It's an ordinary game of the crew's, logged by Sam.
    games = people.client.get(f"/v1/groups/{crew['gid']}/matches", headers=crew["jo"]).json()
    assert [g["id"] for g in games] == [court["match_id"]]
    # A member can't overwrite it.
    again = score(people, crew, event, 1, crew["jo"], games=[{"team_a": 3, "team_b": 11}])
    assert again.status_code == 409
    # A lead can, and it stays the same game.
    fixed = score(people, crew, event, 1, crew["casey"], games=[{"team_a": 9, "team_b": 11}])
    assert fixed.status_code == 200, fixed.text
    court = fixed.json()["round_list"][0]["courts"][0]
    assert (court["winner"], court["match_id"]) == ("B", games[0]["id"])
    # A bad score gets the same message as logging a game.
    bad_score = [{"team_a": 11, "team_b": 10}]
    bad = score(people, crew, event, 2, crew["sam"], games=bad_score)
    court2 = event["round_list"][0]["courts"][1]
    logged = people.client.post(
        f"/v1/groups/{crew['gid']}/matches",
        json={
            "format": "doubles",
            "points_to": 11,
            "win_by_two": True,
            "best_of": 1,
            "team_a": court2["team_a"],
            "team_b": court2["team_b"],
            "games": bad_score,
        },
        headers=crew["sam"],
    )
    assert bad.status_code == logged.status_code == 422
    assert bad.json()["detail"] == logged.json()["detail"]


def test_deleting_the_game_empties_the_court(people: People, crew: dict[str, Any]) -> None:
    event = start(people, crew).json()
    match_id = score(people, crew, event, 1, crew["sam"]).json()["round_list"][0]["courts"][0][
        "match_id"
    ]
    gone = people.client.delete(f"/v1/groups/{crew['gid']}/matches/{match_id}", headers=crew["sam"])
    assert gone.status_code == 204
    court = people.client.get(url(crew, event), headers=crew["sam"]).json()["round_list"][0][
        "courts"
    ][0]
    assert (court["match_id"], court["winner"]) == (None, None)


def test_the_next_round_waits_for_every_court(people: People, crew: dict[str, Any]) -> None:
    event = start(people, crew).json()
    early = people.client.post(url(crew, event, "/rounds"), headers=crew["casey"])
    assert early.status_code == 409
    score(people, crew, event, 1, crew["sam"])
    # Court 2 couldn't finish: a lead skips it.
    member_skip = people.client.post(
        url(crew, event, "/courts/skip"), json={"round": 1, "court": 2}, headers=crew["sam"]
    )
    assert member_skip.status_code == 403
    skip = people.client.post(
        url(crew, event, "/courts/skip"), json={"round": 1, "court": 2}, headers=crew["casey"]
    )
    assert skip.json()["can_start_round"] is True
    assert people.client.post(url(crew, event, "/rounds"), headers=crew["sam"]).status_code == 403
    second = people.client.post(url(crew, event, "/rounds"), headers=crew["casey"])
    assert second.status_code == 201
    assert [r["number"] for r in second.json()["round_list"]] == [1, 2]
    # Whoever sat out round 1 plays in round 2.
    [sat] = second.json()["round_list"][0]["sitting_out"]
    assert sat not in second.json()["round_list"][1]["sitting_out"]


def test_people_arrive_and_leave(people: People, crew: dict[str, Any]) -> None:
    event = start(people, crew, players=list(crew["ids"].values())[:8]).json()
    late = next(
        i
        for i in crew["ids"].values()
        if i not in event["round_list"][0]["sitting_out"]
        and all(i not in c["team_a"] + c["team_b"] for c in event["round_list"][0]["courts"])
    )
    leaver = event["round_list"][0]["courts"][0]["team_a"][0]
    assert (
        people.client.post(
            url(crew, event, "/players"), json={"player_id": late}, headers=crew["casey"]
        ).status_code
        == 204
    )
    assert (
        people.client.post(
            url(crew, event, f"/players/{leaver}/leave"), headers=crew["casey"]
        ).status_code
        == 204
    )
    for c in (1, 2):
        score(people, crew, event, c, crew["sam"])
    second = people.client.post(url(crew, event, "/rounds"), headers=crew["casey"]).json()
    on_court = {p for c in second["round_list"][1]["courts"] for p in c["team_a"] + c["team_b"]}
    assert late in on_court
    assert leaver not in on_court | set(second["round_list"][1]["sitting_out"])
    # Someone from another crew can't be added.
    other_lead = people.new("Robin")
    other = create(people, other_lead, "Other")["id"]
    robin = next(iter(players(people, other_lead, other).values()))["id"]
    foreign = people.client.post(
        url(crew, event, "/players"), json={"player_id": robin}, headers=crew["casey"]
    )
    assert foreign.status_code == 422


def test_strangers_see_nothing(people: People, crew: dict[str, Any]) -> None:
    event = start(people, crew).json()
    stranger = people.new("Robin")
    assert people.client.get(url(crew, event), headers=stranger).status_code == 404
    assert score(people, crew, event, 1, stranger).status_code == 404
    other_lead = people.new("Morgan")
    other = create(people, other_lead, "Other Crew")["id"]
    # An event id from another crew isn't found under your own crew.
    wrong = people.client.get(f"/v1/groups/{other}/events/{event['id']}", headers=other_lead)
    assert wrong.status_code == 404


def test_competitive_events_show_standings_and_social_ones_only_yours(
    people: People, crew: dict[str, Any]
) -> None:
    social = start(people, crew).json()
    after = score(people, crew, social, 1, crew["sam"]).json()
    assert after["standings"] is None
    competitive = start(people, crew, name="Cup Day", vibe="competitive").json()
    done = score(people, crew, competitive, 1, crew["sam"]).json()
    table = done["standings"]
    assert len(table) == 4
    assert [row["wins"] for row in table] == [1, 1, 0, 0]
    assert table[0]["points_for"] == 11


def test_event_games_count_like_any_game(people: People, crew: dict[str, Any]) -> None:
    event = start(people, crew).json()
    court = event["round_list"][0]["courts"][0]
    casey_player = crew["ids"]["Casey"]
    score(people, crew, event, 1, crew["sam"])
    score(people, crew, event, 2, crew["sam"])
    # Crew points: whoever played has a game on the record.
    board = people.client.get(f"/v1/groups/{crew['gid']}/board", headers=crew["casey"]).json()
    played = {
        row["player_id"]: row["matches"]
        for section in ("ranked", "getting_started", "resting")
        for row in board[section]
    }
    for p in court["team_a"] + court["team_b"]:
        assert played[p] == 1
    # Recaps see the day: the event's two games and one logged as usual.
    logged = log(
        people,
        crew["casey"],
        crew["gid"],
        format="singles",
        team_a=[crew["ids"]["Ana"]],
        team_b=[crew["ids"]["Bo"]],
        games=[{"team_a": 11, "team_b": 4}],
    )
    assert logged.status_code == 201, logged.text
    recaps = people.client.get(f"/v1/groups/{crew['gid']}/recaps", headers=crew["casey"]).json()
    assert recaps
    assert recaps[0]["games"] == 3
    # Your week counts it for whoever played.
    on_court = {p for c in event["round_list"][0]["courts"] for p in c["team_a"] + c["team_b"]}
    week = people.client.get("/v1/me/week", headers=crew["casey"]).json()
    assert week["games"] == (1 if casey_player in on_court else 0)


def test_river_starts_in_order_and_moves_winners_up(
    people: People, crew: dict[str, Any], lists: Lists
) -> None:
    lists.add("events.river", crew["gid"])
    eight = list(crew["ids"].values())[:8]
    event = start(people, crew, kind="river", name="River", players=eight, seeding="random")
    assert event.status_code == 201, event.text
    event = event.json()
    first = event["round_list"][0]
    top, bottom = first["courts"]
    # Team A wins on top, team B on the bottom.
    score(people, crew, event, 1, crew["sam"], games=[{"team_a": 11, "team_b": 5}])
    score(people, crew, event, 2, crew["sam"], games=[{"team_a": 4, "team_b": 11}])
    second = people.client.post(url(crew, event, "/rounds"), headers=crew["casey"]).json()
    new_top = second["round_list"][1]["courts"][0]
    assert set(new_top["team_a"] + new_top["team_b"]) == set(top["team_a"] + bottom["team_b"])
    # A starting order is never sent.
    assert "start_rank" not in repr(second)
    # Only River takes a starting order.
    assert start(people, crew, seeding="random").status_code == 422
    assert start(people, crew, kind="river", name="No order").status_code == 422


def test_a_crew_runs_at_most_three_events(people: People, crew: dict[str, Any]) -> None:
    for i in range(3):
        assert start(people, crew, name=f"Event {i}").status_code == 201
    assert start(people, crew, name="One more").status_code == 409


def test_only_this_courts_game_can_fill_it(
    people: People, crew: dict[str, Any], app_engine: Engine
) -> None:
    event = start(people, crew).json()
    # Some other game in the crew.
    other = people.client.post(
        f"/v1/groups/{crew['gid']}/matches",
        json={
            "format": "doubles",
            "points_to": 11,
            "win_by_two": True,
            "best_of": 1,
            "team_a": event["round_list"][0]["courts"][1]["team_a"],
            "team_b": event["round_list"][0]["courts"][1]["team_b"],
            "games": [{"team_a": 11, "team_b": 2}],
        },
        headers=crew["sam"],
    ).json()["id"]
    sam = people.user_id(crew["sam"])
    with as_user(app_engine, sam) as conn:
        # Not this event's game: refused.
        outcome = conn.execute(
            text("SELECT app_score_court(:e, 1::smallint, 2::smallint, :m)"),
            {"e": event["id"], "m": other},
        ).scalar_one()
        assert outcome == "wrong_game"
        # And nobody links a court directly.
        assert (
            sqlstate_of(
                conn,
                "UPDATE event_courts SET match_id = :m WHERE event_id = :e",
                {"m": other, "e": event["id"]},
            )
            == INSUFFICIENT_PRIVILEGE
        )
    # This event's game, but from court 2: not court 1's players, so refused.
    court2 = score(people, crew, event, 2, crew["sam"]).json()["round_list"][0]["courts"][1]
    with as_user(app_engine, sam) as conn:
        outcome = conn.execute(
            text("SELECT app_score_court(:e, 1::smallint, 1::smallint, :m)"),
            {"e": event["id"], "m": court2["match_id"]},
        ).scalar_one()
        assert outcome == "wrong_game"
    stranger = people.user_id(people.new("Robin"))
    with as_user(app_engine, stranger) as conn:
        outcome = conn.execute(
            text("SELECT app_score_court(:e, 1::smallint, 1::smallint, :m)"),
            {"e": event["id"], "m": other},
        ).scalar_one()
        assert outcome == "no_court"


def both_at_once(*calls: Callable[[], Any]) -> list[int]:
    """Run the calls together, released at the same moment; their status codes."""
    gate = threading.Barrier(len(calls))
    codes: list[int] = [0] * len(calls)

    def run(i: int, call: Callable[[], Any]) -> None:
        gate.wait()
        codes[i] = call().status_code

    threads = [threading.Thread(target=run, args=(i, c)) for i, c in enumerate(calls)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return sorted(codes)


def test_two_scores_at_once_make_one_game(people: People, crew: dict[str, Any]) -> None:
    event = start(people, crew).json()
    codes = both_at_once(
        lambda: score(people, crew, event, 1, crew["sam"]),
        lambda: score(people, crew, event, 1, crew["jo"], games=[{"team_a": 4, "team_b": 11}]),
    )
    assert codes == [200, 409]
    games = people.client.get(f"/v1/groups/{crew['gid']}/matches", headers=crew["jo"]).json()
    assert len(games) == 1
    court = people.client.get(url(crew, event), headers=crew["sam"]).json()["round_list"][0][
        "courts"
    ][0]
    assert court["match_id"] == games[0]["id"]


def test_two_taps_on_next_round_make_one_round(people: People, crew: dict[str, Any]) -> None:
    event = start(people, crew).json()
    for c in (1, 2):
        score(people, crew, event, c, crew["sam"])
    codes = both_at_once(
        lambda: people.client.post(url(crew, event, "/rounds"), headers=crew["casey"]),
        lambda: people.client.post(url(crew, event, "/rounds"), headers=crew["casey"]),
    )
    assert codes == [201, 409]
    rounds = people.client.get(url(crew, event), headers=crew["sam"]).json()["round_list"]
    assert [r["number"] for r in rounds] == [1, 2]


def player_ids(event: dict[str, Any]) -> set[UUID]:
    return {UUID(p["player_id"]) for p in event["people"]}
