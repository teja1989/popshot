import re
from collections.abc import Iterable
from datetime import UTC, date, datetime, timedelta
from itertools import pairwise
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from hypothesis import given
from hypothesis import strategies as st

from popshot_api import recap_lines
from popshot_api.rating import GameScore, PlayedMatch
from popshot_api.recap import (
    ALWAYS_THERE_WEEKS,
    MIN_GAMES,
    Award,
    Outing,
    day_key,
    find,
    outings,
    recap,
    with_recaps,
    zone,
)
from popshot_api.recap_lines import commentary, join_names

# Thursday 1 October 2026, 6pm.
T0 = datetime(2026, 10, 1, 18, tzinfo=UTC)
A, B, C, D, E, F = (uuid4() for _ in range(6))
NAMES = {A: "Ana Ruiz", B: "Bo", C: "Cam Lee", D: "Dee", E: "Eli", F: "Fran"}
CREW = uuid4()
NEW_YORK = ZoneInfo("America/New_York")


def days(matches: Iterable[PlayedMatch], time_zone: str = "UTC") -> list[Outing]:
    return outings(matches, CREW, time_zone)


def match(a: list[UUID], b: list[UUID], *games: tuple[int, int], at: datetime = T0) -> PlayedMatch:
    return PlayedMatch(
        id=uuid4(), played_at=at, team_a=a, team_b=b, games=[GameScore(x, y) for x, y in games]
    )


def kinds(found: tuple[Award, ...]) -> dict[str, Award]:
    return {a.kind: a for a in found}


def test_games_are_grouped_by_the_crews_own_day() -> None:
    # 11:30pm and 12:30am in New York: the same day in UTC, two days for the crew.
    late = match([A], [B], (11, 3), at=datetime(2026, 10, 1, 23, 30, tzinfo=NEW_YORK))
    after_midnight = match([A], [B], (11, 3), at=datetime(2026, 10, 2, 0, 30, tzinfo=NEW_YORK))
    morning = match([A], [B], (11, 3), at=datetime(2026, 10, 1, 8, tzinfo=NEW_YORK))
    found = days([after_midnight, late, morning], "America/New_York")
    assert [o.day for o in found] == [date(2026, 10, 1), date(2026, 10, 2)]
    # Morning and late evening are one day, however long the gap.
    assert [m.id for m in found[0].matches] == [morning.id, late.id]
    assert len(days([after_midnight, late], "UTC")) == 1


def test_a_days_key_never_changes_as_games_come_and_go() -> None:
    games = [match([A], [B], (11, 3), at=T0 + timedelta(minutes=m)) for m in (0, 20, 50)]
    key = days(games)[0].key
    assert key == day_key(CREW, T0.date())
    # A game backdated to earlier that day, or the first game deleted: same key.
    earlier = match([A], [B], (11, 3), at=T0 - timedelta(hours=8))
    assert days([earlier, *games])[0].key == key
    assert days(games[1:])[0].key == key
    # Another crew's day, or another day: another key.
    assert outings(games, uuid4(), "UTC")[0].key != key
    assert day_key(CREW, T0.date() + timedelta(days=1)) != key


@given(st.lists(st.integers(min_value=0, max_value=60 * 24 * 7), max_size=30))
def test_days_keep_every_game_once_in_order(minutes: list[int]) -> None:
    games = [match([A], [B], (11, 3), at=T0 + timedelta(minutes=m)) for m in minutes]
    found = days(games, "America/New_York")
    flat = [m for o in found for m in o.matches]
    assert sorted(m.id for m in flat) == sorted(m.id for m in games)
    assert [m.played_at for m in flat] == sorted(m.played_at for m in games)
    for o in found:
        assert {m.played_at.astimezone(NEW_YORK).date() for m in o.matches} == {o.day}
    assert all(before.day < after.day for before, after in pairwise(found))


def test_a_day_needs_three_games_for_a_recap() -> None:
    two = [match([A], [B], (11, 3), at=T0 + timedelta(minutes=m)) for m in range(MIN_GAMES - 1)]
    three = [match([A], [B], (11, 3), at=T0 + timedelta(days=1, minutes=m)) for m in range(3)]
    found = days([*two, *three])
    assert [o.has_recap for o in found] == [False, True]
    assert find(found, found[0].key) is None
    # The smaller day still counts as history for the one after it.
    assert with_recaps(found) == [(found[1], [found[0]])]


def test_an_unknown_zone_falls_back_to_utc() -> None:
    assert zone("Mars/Olympus_Mons") == UTC
    assert zone("../etc") == UTC
    assert zone(None) == UTC
    assert zone("Asia/Kolkata") == ZoneInfo("Asia/Kolkata")


def test_awards_for_an_outing() -> None:
    first = days([match([A, B], [C, D], (11, 5), at=T0 - timedelta(days=7))])
    today = days(
        [
            match([A, B], [C, D], (11, 9)),  # A&B win by two
            match([A, C], [B, E], (11, 4), at=T0 + timedelta(minutes=20)),  # E is new
            match([A, D], [C, E], (11, 6), at=T0 + timedelta(minutes=40)),
        ]
    )[0]
    found = recap(today, first)
    got = kinds(found.awards)
    assert found.newcomers == (E,)
    # A won with B, C and D: three different partners.
    assert got["great_partner"] == Award("great_partner", (A,), 3)
    # B and C partnered E.
    assert set(got["welcome_wagon"].players) == {B, C}
    assert got["welcome_wagon"].value == 1
    # A and C played 3, more than the 1 each last week; B played 2.
    bests = {a.players[0] for a in found.awards if a.kind == "personal_best"}
    assert bests == {A, C}
    assert set(got["close_call"].players) == {A, B}
    assert got["close_call"].value == 1
    assert "always_there" not in got
    # A and C played most (3 each); order between equals isn't promised.
    assert {pid for pid, n in found.players if n == 3} == {A, C}


def test_close_call_is_a_win_by_one_or_two() -> None:
    today = days(
        [
            match([A], [B], (11, 10)),  # by one (no win by two)
            match([C], [D], (9, 11), at=T0 + timedelta(minutes=20)),  # by two
            match([E], [F], (11, 8), at=T0 + timedelta(minutes=40)),  # by three: not close
        ]
    )[0]
    got = kinds(recap(today, []).awards)
    assert got["close_call"] == Award("close_call", (A, D) if str(A) < str(D) else (D, A), 2)


def test_always_there_needs_four_weeks_running() -> None:
    weekly = [
        match([A], [B], (11, 3), at=T0 - timedelta(weeks=w))
        for w in range(ALWAYS_THERE_WEEKS - 1, 0, -1)
    ]
    all_outings = days([*weekly, match([A], [C], (11, 3))])
    found = recap(all_outings[-1], all_outings[:-1])
    assert kinds(found.awards)["always_there"] == Award("always_there", (A,), ALWAYS_THERE_WEEKS)
    # One week fewer: no award.
    short = days([*weekly[1:], match([A], [C], (11, 3))])
    assert "always_there" not in kinds(recap(short[-1], short[:-1]).awards)


def test_nobody_gets_an_award_for_losing_or_a_first_outing_record() -> None:
    only = days([match([A], [B], (11, 0)), match([A], [B], (11, 1))])
    found = recap(only[0], [])
    # A first outing can't be a personal best, singles has no partners, no close games.
    assert found.awards == ()
    assert set(found.newcomers) == {A, B}


def test_find_returns_the_outing_and_what_came_before() -> None:
    all_outings = days(
        [
            match([A], [B], (11, 3), at=T0 + timedelta(days=d, minutes=m))
            for d in range(3)
            for m in range(MIN_GAMES)
        ]
    )
    found = find(all_outings, all_outings[1].key)
    assert found is not None
    assert found[0] == all_outings[1]
    assert found[1] == all_outings[:1]
    assert find(all_outings, uuid4()) is None


def test_join_names() -> None:
    assert join_names([]) == ""
    assert join_names(["Jo"]) == "Jo"
    assert join_names(["Jo", "Sam"]) == "Jo and Sam"
    assert join_names(["Jo", "Sam", "Pat", "Ana"]) == "Jo, Sam, Pat and Ana"
    assert join_names(["Jo", "Sam", "Pat", "Ana", "Bo"]) == "Jo, Sam, Pat and 2 more"


def all_templates() -> list[str]:
    pools = [
        recap_lines.HEADLINES,
        recap_lines.ONE_GAME,
        recap_lines.WELCOME_ONE,
        recap_lines.WELCOME_MANY,
        recap_lines.QUIET,
        *recap_lines.ONE.values(),
        *recap_lines.MANY.values(),
    ]
    return [line for pool in pools for line in pool]


def test_every_line_fills_in_completely() -> None:
    facts = {"games": 6, "players": 5, "crew": "Sunday Dinkers", "at": "", "names": "Jo", "n": 3}
    for line in all_templates():
        filled = line.format(**facts)
        assert "{" not in filled, line
        assert "}" not in filled, line


def test_lines_stay_friendly() -> None:
    # Nobody is mocked for losing, and nobody is called he or she.
    banned = re.compile(r"\b(he|she|him|her|his|hers|lost|loser|losing|worst|beat|crushed)\b", re.I)
    for line in all_templates():
        assert not banned.search(line), line


def test_commentary_uses_first_names_and_reads_the_same_every_time() -> None:
    first = days([match([A, B], [C, D], (11, 5), at=T0 - timedelta(days=7))])
    today = days(
        [
            match([A, B], [C, E], (11, 9)),
            match([A, C], [B, E], (11, 4), at=T0 + timedelta(minutes=20)),
        ]
    )[0]
    found = recap(today, first)
    said = commentary(found, NAMES, "Sunday Dinkers", "Riverside courts")
    assert said == commentary(found, NAMES, "Sunday Dinkers", "Riverside courts")
    text = " ".join([said.headline, *said.lines])
    # First names only; never a surname.
    assert "Ruiz" not in text
    assert "Lee" not in text
    assert said.lines[0].count("Eli") == 1  # the newcomer is welcomed first
    assert 1 <= len(said.lines) <= recap_lines.MAX_LINES
    # Only names of people who played.
    mentioned = set(re.findall(r"\b[A-Z][a-z]+\b", text))
    assert mentioned & {"Dee", "Fran"} == set()


def test_quiet_outing_still_gets_a_friendly_line() -> None:
    only = days([match([A], [B], (11, 3), at=T0 - timedelta(days=7)), match([A], [B], (11, 3))])
    said = commentary(recap(only[1], only[:1]), NAMES, "Crew", None)
    assert said.headline.startswith(("One game", "A quick one"))
    assert said.lines[0] in recap_lines.QUIET


def test_counts_read_right_even_for_one() -> None:
    # Awards that can be about a single game must not say "1 games".
    for pool in (recap_lines.ONE["close_call"], recap_lines.MANY["close_call"]):
        for line in pool:
            filled = line.format(names="Jo and Sam", n=1)
            assert "1 games" not in filled, line


def test_hidden_people_are_not_named() -> None:
    # Eli is new and partners Ana; Bo and Eli win close games.
    first = days([match([A, B], [C, D], (11, 5), at=T0 - timedelta(days=7))])
    today = days(
        [
            match([A, E], [C, D], (11, 9)),
            match([B, E], [C, D], (11, 9), at=T0 + timedelta(minutes=20)),
        ]
    )[0]
    found = recap(today, first)
    said = commentary(found, NAMES, "Crew", None, hidden={E})
    text = " ".join([said.headline, *said.lines])
    assert "Eli" not in text
    # A line about only Eli (the welcome) is left out; shared lines say "and 1 more".
    welcomes = [
        re.compile(re.escape(t).replace(re.escape("{names}"), ".*"))
        for t in recap_lines.WELCOME_ONE
    ]
    assert not any(w.fullmatch(line) for w in welcomes for line in said.lines)
    assert any(
        w.fullmatch(line) for w in welcomes for line in commentary(found, NAMES, "C", None).lines
    )
    assert "and 1 more" in text
    assert said.lines
    # Nothing hidden: the same as before.
    assert commentary(found, NAMES, "Crew", None, hidden=set()) == commentary(
        found, NAMES, "Crew", None
    )
