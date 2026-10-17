from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest

from popshot_api.ai_recap import MAX_HEADLINE, MAX_LINE, check, facts_for, facts_hash
from popshot_api.rating import GameScore, PlayedMatch
from popshot_api.recap import outings, recap

T0 = datetime(2026, 10, 1, 18, tzinfo=UTC)
A, B, C, D = (uuid4() for _ in range(4))
NAMES = {A: "Ana Ruiz", B: "Bo", C: "Cam Lee", D: "Dee"}
CREW = {"Ana", "Bo", "Cam", "Dee"}


def match(a: list[UUID], b: list[UUID], score: tuple[int, int], at: datetime) -> PlayedMatch:
    return PlayedMatch(id=uuid4(), played_at=at, team_a=a, team_b=b, games=[GameScore(*score)])


def outing_facts() -> dict[str, Any]:
    # Last week Ana played Dee; today Ana and Bo play Cam twice (one won by two). Bo and Cam
    # are new.
    all_outings = outings(
        [
            match([A], [D], (11, 4), T0 - timedelta(days=7)),
            match([A, B], [C], (11, 9), T0),
            match([A, B], [C], (11, 5), T0 + timedelta(minutes=15)),
        ],
        uuid4(),
        "UTC",
    )
    found = recap(all_outings[-1], all_outings[:-1])
    return facts_for(found, NAMES, "Lunch Dinkers", "Riverside courts")


def reply(headline: str = "Paddles up, Lunch Dinkers!", *lines: str) -> dict[str, Any]:
    return {"headline": headline, "lines": list(lines or ["Ana and Bo kept the rallies going."])}


def test_facts_are_first_names_counts_and_awards_only() -> None:
    facts = outing_facts()
    assert facts["games"] == 2
    assert {p["name"] for p in facts["players"]} == {"Ana", "Bo", "Cam"}
    assert set(facts["first_timers"]) == {"Bo", "Cam"}
    assert {a["award"] for a in facts["awards"]} >= {"Close Call"}
    flat = repr(facts)
    assert "Ruiz" not in flat
    assert "Lee" not in flat


def test_facts_hash_changes_with_facts_and_model() -> None:
    facts = outing_facts()
    same = facts_hash(facts, "gemini-a")
    assert same == facts_hash(dict(facts), "gemini-a")
    assert same != facts_hash(facts, "gemini-b")
    assert same != facts_hash({**facts, "games": 3}, "gemini-a")


def test_a_good_reply_passes_tidied() -> None:
    said = check(
        reply("  Paddles up,\nLunch Dinkers! ", "Welcome, Cam! 2 games in the books."),
        outing_facts(),
        CREW,
    )
    assert said is not None
    assert said.headline == "Paddles up, Lunch Dinkers!"
    assert said.lines == ("Welcome, Cam! 2 games in the books.",)


@pytest.mark.parametrize(
    ("raw", "why"),
    [
        ({"headline": "Hi", "lines": ["One"], "extra": 1}, "extra field"),
        ({"headline": 5, "lines": ["One"]}, "wrong type"),
        ("Paddles up!", "not an object"),
        (reply("Hi", "a", "b", "c", "d"), "too many lines"),
        (reply("x" * (MAX_HEADLINE + 1)), "headline too long"),
        (reply("Hi", "x" * (MAX_LINE + 1)), "line too long"),
        (reply("Hi", "Dee watched from the kitchen."), "names someone who didn't play"),
        (reply("Hi", "Ana won 7 games!"), "a number that isn't in the facts"),
        (reply("Hi", "Cam lost twice but smiled."), "mentions losing"),
        (reply("Hi", "Bo and his partner were great."), "his/her"),
        (reply("Hi", "Cam was too slow today."), "teasing"),
        (reply("Hi", "More at https://example.com"), "a link"),
        (reply("Hi", "Shout out to #crew"), "a hashtag"),
    ],
)
def test_replies_that_break_a_rule_are_refused(raw: Any, why: str) -> None:
    assert check(raw, outing_facts(), CREW) is None, why


def test_a_reply_with_no_lines_is_refused() -> None:
    assert check({"headline": "Hi", "lines": []}, outing_facts(), CREW) is None
