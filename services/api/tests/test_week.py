from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from popshot_api.rating import GameScore, PlayedMatch
from popshot_api.week import CrewWeek, in_window, summarize

NOW = datetime(2026, 10, 12, 20, tzinfo=UTC)
ME, ALEX, SAM, JO = (uuid4() for _ in range(4))
NAMES = {ME: "Casey", ALEX: "Alex", SAM: "Sam", JO: "Jo"}


def match(a: list[UUID], b: list[UUID], score: tuple[int, int], days_ago: float) -> PlayedMatch:
    return PlayedMatch(
        id=uuid4(),
        played_at=NOW - timedelta(days=days_ago),
        team_a=a,
        team_b=b,
        games=[GameScore(*score)],
    )


def crew(*matches: PlayedMatch, name: str = "Lunch Dinkers", me: UUID = ME) -> CrewWeek:
    return CrewWeek(crew=name, me=me, matches=list(matches), names=NAMES)


def test_a_busy_week() -> None:
    week = summarize(
        [
            crew(
                match([ME, ALEX], [SAM, JO], (11, 9), 1),
                match([ME, ALEX], [SAM, JO], (11, 4), 2),
                match([ME, SAM], [ALEX, JO], (8, 11), 3),
            )
        ],
        ["third_shot_drop"],
    )
    assert (week.games, week.wins, week.close_games) == (3, 2, 1)
    assert week.longest_win_streak == 2
    assert week.top_partner == ("Alex", 2)
    assert week.headline == "3 games this week."
    assert week.lines == [
        "You won 2 of 3.",
        "A 2-game win streak in there.",
        "One game went down to the wire, decided by 2 points or fewer.",
        "You partnered Alex most (2 games).",
        "You're working on third-shot drops: close games like those are the perfect place to"
        " try it.",
    ]


def test_a_quiet_week_is_warm_not_a_nudge() -> None:
    week = summarize([], ["footwork"])
    assert week.games == 0
    assert week.headline == "A quiet week on court."
    assert "missed" not in " ".join(week.lines)


def test_no_wins_never_dwells_on_losses() -> None:
    week = summarize([crew(match([ME], [SAM], (3, 11), 1))], [])
    text = " ".join([week.headline, *week.lines]).lower()
    assert "lost" not in text
    assert "loss" not in text
    assert "you showed up" in text


def test_across_crews() -> None:
    week = summarize(
        [
            crew(match([ME], [SAM], (11, 2), 1), name="Lunch Dinkers"),
            crew(match([ME], [JO], (11, 9), 2), name="Night Owls"),
        ],
        [],
    )
    assert week.headline == "2 games this week, across 2 crews."
    assert week.crews == ["Lunch Dinkers", "Night Owls"]
    # Singles: no partner to name.
    assert week.top_partner is None


def test_only_the_last_seven_days() -> None:
    inside = match([ME], [SAM], (11, 2), 6.9)
    outside = match([ME], [SAM], (11, 2), 7.1)
    future = match([ME], [SAM], (11, 2), -0.5)
    assert in_window([inside, outside, future], NOW) == [inside]


def test_retired_or_unknown_focus_is_skipped() -> None:
    week = summarize([crew(match([ME], [SAM], (11, 2), 1))], ["not_a_focus", "footwork"])
    assert week.lines[-1] == "You're working on footwork. Keep at it next time out."
