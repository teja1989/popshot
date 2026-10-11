from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from hypothesis import given
from hypothesis import strategies as st

from popshot_api.rating import GameScore, PlayedMatch, replay
from popshot_api.stats import (
    MIN_PAIRING,
    Record,
    best_partner,
    highlights,
    nemesis,
    personal,
    rating_before,
    streaks,
    timeline,
    upset,
)

T0 = datetime(2026, 9, 1, 18, tzinfo=UTC)
A, B, C, D, E = (uuid4() for _ in range(5))


def match(a: list[UUID], b: list[UUID], *games: tuple[int, int], at: datetime = T0) -> PlayedMatch:
    return PlayedMatch(
        id=uuid4(), played_at=at, team_a=a, team_b=b, games=[GameScore(x, y) for x, y in games]
    )


def series(*matches_: PlayedMatch) -> list[PlayedMatch]:
    """Space matches a day apart, in the order given."""
    return [
        PlayedMatch(m.id, T0 + timedelta(days=i), m.team_a, m.team_b, m.games)
        for i, m in enumerate(matches_)
    ]


def test_streaks() -> None:
    assert streaks([]) == (None, 0)
    assert streaks(["W", "W", "L", "W", "W", "W", "L", "L"]) == (("L", 2), 3)
    assert streaks(["L", "W"]) == (("W", 1), 1)


@given(st.lists(st.sampled_from(["W", "L"]), max_size=40))
def test_streaks_agree_with_a_brute_force_count(results: list[str]) -> None:
    current, longest = streaks(results)  # type: ignore[arg-type]
    text = "".join(results)
    assert longest == max((len(run) for run in text.split("L")), default=0)
    if results:
        assert current is not None
        assert current[1] == len(text) - len(text.rstrip(results[-1]))


def test_close_games_and_skunks_count_each_game() -> None:
    games = [
        match([A], [B], (12, 10)),  # close win
        match([A], [B], (11, 10)),  # close win (no win-by-2)
        match([A], [B], (9, 11)),  # close loss
        match([A], [B], (11, 2)),  # skunk given
        match([A], [B], (11, 3)),  # neither
        match([A], [B], (1, 11), (11, 0), (11, 9)),  # skunk taken, skunk given, close win
    ]
    s = personal(series(*games), A, {})
    assert (s.close_won, s.close_lost) == (3, 1)
    assert (s.skunks_given, s.skunks_taken) == (2, 1)
    assert (s.matches, s.wins) == (6, 5)
    # The other side sees the mirror image.
    b = personal(series(*games), B, {})
    assert (b.close_won, b.close_lost, b.skunks_given, b.skunks_taken) == (1, 3, 1, 2)


def test_upset_is_any_win_by_the_lower_rated_team() -> None:
    m = match([A, B], [C, D], (11, 9))
    assert upset(m, {m.id: (3.40, 3.10)}) is None  # favourites won
    assert upset(m, {m.id: (3.00, 3.00)}) is None  # even
    found = upset(m, {m.id: (3.00, 3.25)})
    assert found is not None
    assert (found.winners, found.losers, found.gap) == ((A, B), (C, D), 0.25)
    # Team B winning as the underdog.
    m2 = match([A], [C], (5, 11))
    found2 = upset(m2, {m2.id: (4.0, 3.5)})
    assert found2 is not None
    assert (found2.winners, found2.gap) == ((C,), 0.5)


def test_upsets_use_ratings_from_before_the_match() -> None:
    # A beats C twice: A is now the favourite, so C winning next is an upset.
    games = series(match([A], [C], (11, 2)), match([A], [C], (11, 3)), match([A], [C], (8, 11)))
    pregame: dict[UUID, tuple[float, float]] = {}
    replay(games, {}, pregame)
    first = pregame[games[0].id]
    assert first == (3.0, 3.0)
    c = personal(games, C, pregame)
    assert c.upset_wins == 1
    assert c.biggest_upset is not None
    assert c.biggest_upset.match_id == games[2].id
    assert personal(games, A, pregame).upset_wins == 0


def test_best_partner_needs_enough_games_and_breaks_ties_on_games() -> None:
    assert best_partner({B: Record(MIN_PAIRING - 1, MIN_PAIRING - 1)}) is None
    found = best_partner({B: Record(5, 4), C: Record(10, 8), D: Record(4, 4), E: Record(6, 3)})
    assert found is not None
    assert found[0] == C  # same 80% as B, more games together


def test_nemesis_needs_a_losing_record() -> None:
    assert nemesis({B: Record(6, 3)}) is None  # even, not a nemesis
    assert nemesis({B: Record(4, 0)}) is None  # not enough games
    found = nemesis({B: Record(6, 2), C: Record(5, 1), D: Record(10, 2)})
    assert found is not None
    assert found[0] == D  # 20% over 10 beats 20% over 5


def test_partners_and_opponents_are_tallied_by_match() -> None:
    games = series(
        match([A, B], [C, D], (11, 5)),
        match([A, B], [C, E], (4, 11)),
        match([A, C], [B, D], (11, 7)),
    )
    s = personal(games, A, {})
    assert (s.partners[B].played, s.partners[B].won) == (2, 1)
    assert (s.partners[C].played, s.partners[C].won) == (1, 1)
    assert (s.opponents[C].played, s.opponents[C].won) == (2, 1)
    assert (s.opponents[D].played, s.opponents[D].won) == (2, 2)
    assert A not in s.partners


def test_crew_highlights() -> None:
    now = T0 + timedelta(days=60)
    old = [match([A], [B], (11, 3), at=T0 + timedelta(days=i)) for i in range(4)]
    recent = [
        match([C], [B], (11, 5), at=now - timedelta(days=3)),
        match([C], [D], (11, 6), at=now - timedelta(days=2)),
        match([B], [A], (11, 9), at=now - timedelta(days=1)),
    ]
    games = old + recent
    pregame: dict[UUID, tuple[float, float]] = {}
    rated = replay(games, {}, pregame)
    h = highlights(games, rated, pregame, {A, B, C, D}, now)
    # A won 4 in a row, longer than C's 2.
    assert h.streak == (A, 4)
    # Only the last 30 days count for games: B played 2, C played 2; ties are stable.
    assert h.most_games is not None
    assert h.most_games[1] == 2
    # B (beaten four times) beating A is the upset.
    assert h.biggest_upset is not None
    assert h.biggest_upset.winners == (B,)

    # Someone no longer listed (left the group) can't hold a highlight.
    assert highlights(games, rated, pregame, {B, C, D}, now).streak == (C, 2)


def test_highlights_with_no_games() -> None:
    h = highlights([], {}, {}, {A}, T0)
    assert (h.streak, h.most_games, h.biggest_upset) == (None, None, None)


def test_timeline_follows_your_matches_with_ratings() -> None:
    games = series(
        match([A, B], [C, D], (11, 5)),
        match([C], [D], (11, 4)),  # not A's
        match([A], [C], (3, 11)),
    )
    rated = replay(games, {})
    points = timeline(games, A, rated[A])
    assert [(p.doubles, p.won) for p in points] == [(True, True), (False, False)]
    assert points[0].rating > 3.0 > points[1].rating
    assert points[-1].rating == rated[A].rating
    assert [p.played_at for p in points] == [games[0].played_at, games[2].played_at]


def test_rating_before_a_window() -> None:
    games = series(match([A], [B], (11, 5)), match([A], [B], (11, 7)))
    rated = replay(games, {A: 4.0})
    # Before any match: the start. Between the two: after the first.
    assert rating_before(rated[A], 4.0, T0 - timedelta(days=1)) == 4.0
    assert rating_before(rated[A], 4.0, T0 + timedelta(hours=1)) == rated[A].history[0][1]
